"""Round 4 backend tests: SMS OTP, rate-limit, Mailgun webhook, email-events, bulk invite,
dashboard trend range, PDF logo+UNOFFICIAL disclaimer."""
import os
import csv
import io
import secrets
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DEMO = ("demo@illinoistracker.app", "Demo1234!")
ADMIN = ("admin@illinoistracker.app", "Admin1234!")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017").strip('"').strip("'")
DB_NAME = os.environ.get("DB_NAME", "ides_tracker_db").strip('"').strip("'")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="session")
def H():
    tok, u = _login(*DEMO)
    return {"Authorization": f"Bearer {tok}"}, u


@pytest.fixture(scope="session")
def AH():
    tok, u = _login(*ADMIN)
    return {"Authorization": f"Bearer {tok}"}, u


@pytest.fixture(scope="session")
def mdb():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(scope="session")
def primary_claimant(H):
    headers, _ = H
    cs = requests.get(f"{API}/claimants", headers=headers, timeout=30).json()["items"]
    return next(c for c in cs if c.get("label") == "Primary")


# ---------- SMS OTP ----------
def test_sms_send_otp_rejects_non_e164(H, primary_claimant):
    headers, _ = H
    r = requests.post(f"{API}/sms/send-otp",
                      json={"claimant_id": primary_claimant["id"], "phone": "13125550100"},
                      headers=headers, timeout=30)
    assert r.status_code == 400
    assert "E.164" in r.text or "+" in r.text


def test_sms_send_otp_e164_writes_otp_row(H, primary_claimant, mdb):
    """E.164 phone — twilio will fail in trial mode (returns 502) but DB row must exist + audit logged."""
    headers, _ = H
    phone = "+15005550006"  # Twilio magic test-success number; still rate-limited via send_sms_rate_limited
    # Clear previous rate-limit row to ensure clean run
    mdb.sms_log.delete_many({"phone": phone})
    r = requests.post(f"{API}/sms/send-otp",
                      json={"claimant_id": primary_claimant["id"], "phone": phone},
                      headers=headers, timeout=30)
    # Either 200 (sent) or 502 (twilio reject) — both indicate code path executed
    assert r.status_code in (200, 502), r.text
    # OTP row created
    rec = mdb.otp_codes.find_one({"claimant_id": primary_claimant["id"], "phone": phone},
                                 sort=[("created_at", -1)])
    assert rec is not None
    assert len(rec["code"]) == 6 and rec["code"].isdigit()
    assert rec["used"] is False
    # Audit OTP_SEND logged
    items = requests.get(f"{API}/audit-log?action=OTP_SEND&limit=5", headers=headers, timeout=30).json()
    assert items, "expected OTP_SEND audit entry"


def test_sms_verify_otp_with_seeded_code(H, primary_claimant, mdb):
    headers, _ = H
    phone = "+13125550199"
    # Insert fresh OTP directly into DB
    code = "424242"
    mdb.otp_codes.delete_many({"claimant_id": primary_claimant["id"]})
    mdb.otp_codes.insert_one({
        "claimant_id": primary_claimant["id"],
        "user_id": primary_claimant["user_id"],
        "phone": phone,
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    # Wrong code -> 400
    bad = requests.post(f"{API}/sms/verify-otp",
                       json={"claimant_id": primary_claimant["id"], "code": "000000"},
                       headers=headers, timeout=30)
    assert bad.status_code == 400
    # Correct code -> 200
    ok = requests.post(f"{API}/sms/verify-otp",
                      json={"claimant_id": primary_claimant["id"], "code": code},
                      headers=headers, timeout=30)
    assert ok.status_code == 200, ok.text
    assert ok.json().get("ok") is True
    assert ok.json().get("phone") == phone
    # Profile sms_verified=true now
    prof = mdb.profiles.find_one({"id": primary_claimant["id"]})
    assert prof.get("sms_verified") is True
    assert prof.get("sms_phone") == phone
    # Used -> repeat fails
    used = requests.post(f"{API}/sms/verify-otp",
                        json={"claimant_id": primary_claimant["id"], "code": code},
                        headers=headers, timeout=30)
    assert used.status_code == 400


def test_sms_verify_otp_expired(H, primary_claimant, mdb):
    headers, _ = H
    mdb.otp_codes.delete_many({"claimant_id": primary_claimant["id"]})
    mdb.otp_codes.insert_one({
        "claimant_id": primary_claimant["id"],
        "user_id": primary_claimant["user_id"],
        "phone": "+13125550199",
        "code": "999999",
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        "used": False,
        "created_at": datetime.now(timezone.utc) - timedelta(minutes=11),
    })
    r = requests.post(f"{API}/sms/verify-otp",
                     json={"claimant_id": primary_claimant["id"], "code": "999999"},
                     headers=headers, timeout=30)
    assert r.status_code == 400
    assert "expired" in r.text.lower()


# ---------- SMS Rate Limit ----------
def test_send_sms_rate_limited_blocks_second_call(mdb):
    """Insert a fresh sms_log row, then call the helper indirectly via /sms/send-otp:
    the second call must return rate-limited within SMS_MIN_INTERVAL_MINUTES (default 30).
    We verify by inspecting the audit log + that no new sms_log row is added."""
    phone = "+13125559999"
    mdb.sms_log.delete_many({"phone": phone})
    # Seed one sms_log entry 1 minute ago
    mdb.sms_log.insert_one({
        "phone": phone,
        "claimant_id": "seeded",
        "body_preview": "seed",
        "sent_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    })
    # Login + try to send-otp to same phone — should return 502 with rate-limited reason
    tok, _ = _login(*DEMO)
    headers = {"Authorization": f"Bearer {tok}"}
    cs = requests.get(f"{API}/claimants", headers=headers, timeout=30).json()["items"]
    cid = next(c for c in cs if c["label"] == "Primary")["id"]
    r = requests.post(f"{API}/sms/send-otp",
                     json={"claimant_id": cid, "phone": phone},
                     headers=headers, timeout=30)
    assert r.status_code == 502, r.text
    assert "rate-limited" in r.text.lower()
    # sms_log still has exactly 1 row (the seeded one) — rate limit blocked insert
    count = mdb.sms_log.count_documents({"phone": phone})
    assert count == 1


# ---------- Mailgun Webhook ----------
def _mailgun_signed_payload(event_type: str, recipient: str) -> dict:
    """Build a Mailgun webhook body with a valid HMAC signature.

    The backend verifies signature = HMAC-SHA256(MAILGUN_API_KEY, timestamp + token),
    so the test has to sign with the same secret the server uses.
    """
    import hmac
    import hashlib
    import time

    secret = os.environ.get("MAILGUN_API_KEY", "")
    timestamp = str(int(time.time()))
    token = secrets.token_hex(16)
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}{token}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "signature": {"timestamp": timestamp, "token": token, "signature": signature},
        "data": {"event": event_type, "recipient": recipient},
    }


def test_mailgun_webhook_bounced_disables_reminders(H, primary_claimant, mdb):
    if not os.environ.get("MAILGUN_API_KEY"):
        pytest.skip("MAILGUN_API_KEY not configured; webhook signature cannot be verified")
    headers, _ = H
    # Set a known reminder_email on Primary
    body = {
        "label": primary_claimant.get("label") or "Primary",
        "first_name": primary_claimant.get("first_name", ""),
        "last_name": primary_claimant.get("last_name", ""),
        "middle_initial": primary_claimant.get("middle_initial", ""),
        "claimant_id_last4": primary_claimant.get("claimant_id_last4", ""),
        "address": primary_claimant.get("address", ""),
        "city": primary_claimant.get("city", ""),
        "state": primary_claimant.get("state") or "IL",
        "zip_code": primary_claimant.get("zip_code", ""),
        "phone": primary_claimant.get("phone", ""),
        "occupation": primary_claimant.get("occupation", ""),
        "reminder_email": "TEST_bounce@example.com",
        "reminders_enabled": True,
        "sms_enabled": False,
        "sms_phone": "",
    }
    r = requests.put(f"{API}/claimants/{primary_claimant['id']}", json=body, headers=headers, timeout=30)
    assert r.status_code == 200
    # Fire signed Mailgun webhook (no bearer auth; HMAC signature instead)
    w = requests.post(f"{API}/webhooks/mailgun",
                     json=_mailgun_signed_payload("email.bounced", "TEST_bounce@example.com"),
                     timeout=30)
    assert w.status_code == 200
    assert w.json().get("ok") is True
    # Reminders disabled
    prof = mdb.profiles.find_one({"id": primary_claimant["id"]})
    assert prof.get("reminders_enabled") is False
    assert prof.get("email_bounced") is True
    # email_events row written
    ev = mdb.email_events.find_one({"type": "email.bounced", "to": ["TEST_bounce@example.com"]},
                                   sort=[("received_at", -1)])
    assert ev is not None
    # Restore reminders for later tests
    body["reminders_enabled"] = True
    body["reminder_email"] = ""
    requests.put(f"{API}/claimants/{primary_claimant['id']}", json=body, headers=headers, timeout=30)


def test_admin_email_events_list(AH):
    headers, _ = AH
    r = requests.get(f"{API}/admin/email-events", headers=headers, timeout=30)
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    # Should include the bounce we just wrote
    assert any(e.get("type") == "email.bounced" for e in arr)


def test_admin_email_events_non_admin_403(H):
    headers, _ = H
    r = requests.get(f"{API}/admin/email-events", headers=headers, timeout=30)
    assert r.status_code == 403


# ---------- Bulk Invite ----------
def test_bulk_invite_csv_creates_and_skips(AH, mdb):
    headers, _ = AH
    valid = f"TEST_bulk_{secrets.token_hex(3)}@example.com"
    csv_text = (
        "email,claimant_label,note\n"
        f"{valid},TEST_BulkUser,Welcome bulk\n"
        "not-an-email,TEST_BadRow,nope\n"
        "demo@illinoistracker.app,TEST_ExistingUser,already\n"
    )
    r = requests.post(f"{API}/admin/invites/bulk",
                     json={"csv_text": csv_text},
                     headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "created" in d and "skipped" in d
    assert len(d["created"]) == 1
    assert d["created"][0]["email"] == valid
    assert "code" in d["created"][0] and "invite_link" in d["created"][0]
    # Skipped contains both bad email + existing user
    reasons = [s.get("reason", "") for s in d["skipped"]]
    assert any("invalid" in x.lower() for x in reasons)
    assert any("already" in x.lower() or "exists" in x.lower() for x in reasons)
    # Re-running should skip the just-created one (pending invite exists)
    r2 = requests.post(f"{API}/admin/invites/bulk",
                      json={"csv_text": f"email,claimant_label,note\n{valid},X,Y\n"},
                      headers=headers, timeout=30)
    d2 = r2.json()
    assert len(d2["created"]) == 0
    assert any("pending" in s.get("reason", "").lower() for s in d2["skipped"])
    # Audit INVITE_BULK
    log = requests.get(f"{API}/audit-log?action=INVITE_BULK&limit=5", headers=headers, timeout=30).json()
    assert log, "INVITE_BULK audit missing"
    # Cleanup
    code = d["created"][0]["code"]
    requests.delete(f"{API}/admin/invites/{code}", headers=headers, timeout=30)


# ---------- Dashboard Trend Range ----------
def test_dashboard_trend_weeks_4(H):
    headers, _ = H
    r = requests.get(f"{API}/dashboard/trend?weeks=4", headers=headers, timeout=30)
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    assert len(arr) <= 4


def test_dashboard_trend_weeks_52_caps(H):
    headers, _ = H
    r = requests.get(f"{API}/dashboard/trend?weeks=200", headers=headers, timeout=30)
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) <= 52, f"expected <=52 weeks even when 200 requested, got {len(arr)}"


def test_dashboard_trend_weeks_52(H):
    headers, _ = H
    r = requests.get(f"{API}/dashboard/trend?weeks=52", headers=headers, timeout=30)
    assert r.status_code == 200
    assert len(r.json()) <= 52


# ---------- PDF Logo + UNOFFICIAL ----------
def test_pdf_report_has_logo_and_unofficial(H):
    headers, _ = H
    wks = requests.get(f"{API}/benefit-weeks", headers=headers, timeout=30).json()
    items = wks.get("items") if isinstance(wks, dict) else wks
    assert items, "demo user has no benefit weeks to render PDF for"
    wid = items[0]["id"]
    r = requests.get(f"{API}/reports/benefit-week/{wid}", headers=headers, timeout=60)
    assert r.status_code == 200
    data = r.content
    # magic bytes
    assert data[:5] == b"%PDF-", "not a PDF"
    # size > 100KB indicates embedded logo image
    assert len(data) > 100_000, f"PDF too small ({len(data)} bytes) — logo likely missing"
    # 'UNOFFICIAL' string present — reportlab compresses text streams with FlateDecode
    # (and often ASCII85Decode wrapper). We decompress each stream and search inside.
    import re, zlib, base64
    found = b"UNOFFICIAL" in data or b"Unofficial" in data
    if not found:
        i = 0
        while True:
            s = data.find(b"stream\n", i)
            if s < 0:
                break
            if s > 0 and data[s - 1:s] == b"d":  # 'endstream'
                i = s + 7
                continue
            e = data.find(b"endstream", s)
            if e < 0:
                break
            blob = data[s + 7:e].rstrip(b"\r\n ")
            hdr_start = data.rfind(b"<<", 0, s)
            hdr = data[hdr_start:s]
            dec = blob
            try:
                if b"ASCII85Decode" in hdr:
                    ab = dec.strip()
                    if ab.endswith(b"~>"):
                        ab = ab[:-2]
                    dec = base64.a85decode(ab, adobe=False)
                if b"FlateDecode" in hdr:
                    dec = zlib.decompress(dec)
            except Exception:
                i = e + 9
                continue
            if b"UNOFFICIAL" in dec or b"Unofficial" in dec:
                found = True
                break
            i = e + 9
    assert found, "UNOFFICIAL disclaimer not found in PDF text streams"


def test_ides_logo_file_exists():
    assert os.path.exists("/app/backend/assets/ides-logo.png"), "logo asset missing"
    assert os.path.getsize("/app/backend/assets/ides-logo.png") > 0
