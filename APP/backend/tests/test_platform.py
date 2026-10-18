"""Platform tests: tiers, roles, audit trail, SMS OTP, Mailgun bounces, admin.

Replaces test_round2.py, test_round3.py and test_round4.py. Those logged in
with hardcoded demo/admin passwords through /auth/login, which went away with
the Clerk migration, along with several endpoints they covered: /claimants,
/invite/redeem, forgot/reset password and the password_resets TTL index.
Everything here authenticates through the Clerk stub (tests/clerk_stub.py),
the same real RS256 path production uses.

Admin tests need ADMIN_EMAILS set in the backend's environment (CI sets it)
and skip otherwise. The Mailgun bounce test needs MAILGUN_WEBHOOK_SIGNING_KEY.
"""
import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
API = f"{BASE_URL}/api"
CLERK_STUB = os.environ.get("CLERK_STUB_URL", "http://127.0.0.1:8799").rstrip("/")
ADMIN_EMAIL = next(
    (e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()),
    None,
)
needs_admin = pytest.mark.skipif(not ADMIN_EMAIL, reason="ADMIN_EMAILS not configured")

ONBOARDING = {
    "first_name": "Plat", "last_name": "Form", "phone": "(312) 555-0102",
    "sms_opt_in": False, "dob": "1990-01-01", "address": "200 E Randolph St",
    "city": "Chicago", "zip": "60601", "knows_next_cert_date": "na",
}


# ---------- helpers & fixtures ----------
@pytest.fixture(scope="module")
def mdb():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    return MongoClient(url)[os.environ.get("DB_NAME", "ci_test_db")]


def _headers(email=None):
    r = requests.post(
        f"{CLERK_STUB}/__test__/token",
        json={"email": email or f"ci-plat-{uuid.uuid4().hex[:10]}@example.com"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _onboarded(mdb, tier=None):
    """A fresh user with one claimant profile, optionally on a paid tier."""
    h = _headers()
    r = requests.post(f"{API}/auth/onboarding", json=ONBOARDING, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    profile = r.json()
    if tier:
        mdb.subscriptions.update_one(
            {"user_id": profile["user_id"]},
            {"$set": {
                "user_id": profile["user_id"], "tier": tier, "status": "active",
                "current_period_end": datetime.now(timezone.utc) + timedelta(days=30),
            }},
            upsert=True,
        )
    return h, profile


@pytest.fixture(scope="module")
def free_user(mdb):
    return _onboarded(mdb)


@pytest.fixture(scope="module")
def pro_user(mdb):
    return _onboarded(mdb, tier="pro")


@pytest.fixture(scope="module")
def AH():
    if not ADMIN_EMAIL:
        pytest.skip("ADMIN_EMAILS not configured")
    h = _headers(ADMIN_EMAIL)
    me = requests.get(f"{API}/auth/me", headers=h, timeout=30).json()
    assert me["role"] == "admin", f"ADMIN_EMAILS bootstrap did not grant admin: {me}"
    return h


def _week(h, start="2026-02-01", end="2026-02-07"):
    r = requests.post(
        f"{API}/benefit-weeks",
        json={"week_start": start, "week_end": end, "notes": "TEST_plat", "certified": False},
        headers=h, timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _audit(h, **params):
    r = requests.get(f"{API}/audit-log", params=params, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- tier boundaries ----------
@pytest.mark.parametrize("method,path,body", [
    ("get", "/dashboard/trend", None),
    ("post", "/calendar-events", {"event_date": "2030-01-07", "event_type": "other", "title": "x"}),
    ("get", "/contacts/export.csv", None),  # full-history export is a paid feature
])
def test_free_tier_is_gated(free_user, method, path, body):
    h, _ = free_user
    r = getattr(requests, method)(f"{API}{path}", json=body, headers=h, timeout=30)
    assert r.status_code == 402, f"{path}: {r.status_code} {r.text}"


def test_free_tier_sms_is_gated(free_user):
    h, profile = free_user
    r = requests.post(f"{API}/sms/send-otp", json={"claimant_id": profile["id"], "phone": "+13125550100"}, headers=h, timeout=30)
    assert r.status_code == 402, r.text


# ---------- role boundaries ----------
@pytest.mark.parametrize("method,path", [
    ("get", "/admin/users"),
    ("get", "/admin/email-events"),
    ("get", "/admin/integrations/status"),
    ("get", "/admin/invites"),
    ("post", "/admin/invites/bulk"),
    ("get", "/admin/platform/users"),
])
def test_admin_routes_forbidden_for_users(pro_user, method, path):
    h, _ = pro_user
    r = getattr(requests, method)(f"{API}{path}", json={"csv_text": ""}, headers=h, timeout=30)
    assert r.status_code == 403, f"{path}: {r.status_code} {r.text}"


@needs_admin
def test_admin_list_and_detail(AH, pro_user):
    _, profile = pro_user
    users = requests.get(f"{API}/admin/users", headers=AH, timeout=30).json()
    me = next(u for u in users if u["id"] == profile["user_id"])
    assert {"claimants_count", "weeks_count", "contacts_count"} <= me.keys()
    assert "password_hash" not in me
    r = requests.get(f"{API}/admin/users/{profile['user_id']}", headers=AH, timeout=30)
    assert r.status_code == 200
    assert {"user", "claimants", "weeks"} <= r.json().keys()


@needs_admin
def test_admin_platform_users(AH):
    r = requests.get(f"{API}/admin/platform/users", headers=AH, timeout=30)
    assert r.status_code == 200, r.text
    assert "users" in r.json() and "total" in r.json()


@needs_admin
def test_admin_integrations_status_shape(AH):
    d = requests.get(f"{API}/admin/integrations/status", headers=AH, timeout=30).json()
    assert {"configured", "from", "verified_domain", "fallback_from", "dns_records_url"} <= d["mailgun"].keys()
    assert {"configured", "from_number"} <= d["clicksend"].keys()


@needs_admin
def test_bulk_invite_skips_bad_and_existing_rows(AH, pro_user, mdb):
    _, profile = pro_user
    existing = mdb.users.find_one({"id": profile["user_id"]})["email"]
    csv_text = (
        "email,claimant_label,note\n"
        "not-an-email,TEST_Bad,nope\n"
        f"{existing},TEST_Existing,already\n"
    )
    r = requests.post(f"{API}/admin/invites/bulk", json={"csv_text": csv_text}, headers=AH, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["created"] == []
    reasons = [s["reason"] for s in d["skipped"]]
    assert "invalid email" in reasons and "already a user" in reasons
    assert _audit(AH, action="INVITE_BULK")


# ---------- audit trail ----------
def test_contact_update_writes_diff(pro_user):
    h, _ = pro_user
    wid = _week(h, "2026-04-05", "2026-04-11")
    ct = {"benefit_week_id": wid, "contact_date": "2026-04-06", "employer_name": "TEST_Diff",
          "employer_address": "", "contact_method": "Online", "type_of_work": "",
          "position_applied": "Engineer", "person_contacted": "", "result": "Applied", "source_url": ""}
    cid = requests.post(f"{API}/contacts", json=ct, headers=h, timeout=30).json()["id"]
    requests.put(f"{API}/contacts/{cid}", json={**ct, "result": "Interview"}, headers=h, timeout=30)
    upd = [i for i in _audit(h, action="UPDATE", entity="contact") if i["entity_id"] == cid]
    assert upd and "result" in upd[0]["detail"] and "→" in upd[0]["detail"]


def test_week_update_writes_diff(pro_user):
    h, _ = pro_user
    wk = {"week_start": "2026-05-03", "week_end": "2026-05-09", "notes": "TEST_wk", "certified": False}
    wid = requests.post(f"{API}/benefit-weeks", json=wk, headers=h, timeout=30).json()["id"]
    requests.put(f"{API}/benefit-weeks/{wid}", json={**wk, "notes": "TEST_changed"}, headers=h, timeout=30)
    upd = [i for i in _audit(h, action="UPDATE", entity="benefit_week") if i["entity_id"] == wid]
    assert upd and "notes" in upd[0]["detail"] and "→" in upd[0]["detail"]


def test_profile_update_writes_diff(pro_user):
    h, profile = pro_user
    r = requests.put(f"{API}/profile", json={"label": "Primary", "first_name": "Renamed", "last_name": "Form"}, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    upd = [i for i in _audit(h, action="UPDATE", entity="claimant") if i["entity_id"] == profile["id"]]
    assert upd and "first_name" in upd[0]["detail"]


def test_audit_filters(pro_user):
    h, _ = pro_user
    assert all(i["action"] == "ONBOARDING" for i in _audit(h, action="ONBOARDING"))
    assert all(i["entity"] == "benefit_week" for i in _audit(h, entity="benefit_week"))
    assert isinstance(_audit(h, action="ALL", entity="ALL", limit=5), list)
    hits = _audit(h, q="TEST_Diff")
    assert hits and all("test_diff" in i["detail"].lower() for i in hits)


def test_csv_export_full_history_and_audit(pro_user):
    h, _ = pro_user
    r = requests.get(f"{API}/contacts/export.csv", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("contact_date")
    assert _audit(h, action="EXPORT_CSV")


# ---------- dashboard trend ----------
@pytest.mark.parametrize("weeks,cap", [(4, 4), (52, 52), (200, 52)])
def test_dashboard_trend_caps(pro_user, weeks, cap):
    h, _ = pro_user
    r = requests.get(f"{API}/dashboard/trend", params={"weeks": weeks}, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    arr = r.json()
    assert isinstance(arr, list) and len(arr) <= cap
    starts = [w["week_start"] for w in arr]
    assert starts == sorted(starts)
    for w in arr:
        assert {"week_start", "contacts", "target", "compliant"} <= w.keys()


# ---------- reminders ----------
def test_reminder_rejects_unknown_kind(pro_user):
    h, _ = pro_user
    r = requests.post(f"{API}/reminders/test", params={"kind": "monday"}, headers=h, timeout=30)
    assert r.status_code == 400


def test_reminder_runs_for_verified_user(pro_user):
    """Exercises the reminder path end to end. With Mailgun unconfigured in CI
    nothing is delivered, but the call must not error."""
    h, _ = pro_user
    r = requests.post(f"{API}/reminders/test", params={"kind": "friday"}, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "friday"


# ---------- SMS OTP ----------
def test_sms_otp_rejects_non_e164(pro_user):
    h, profile = pro_user
    r = requests.post(f"{API}/sms/send-otp", json={"claimant_id": profile["id"], "phone": "13125550100"}, headers=h, timeout=30)
    assert r.status_code == 400 and "E.164" in r.text


def test_sms_otp_rejects_foreign_claimant(pro_user, free_user):
    h, _ = pro_user
    _, other = free_user
    r = requests.post(f"{API}/sms/send-otp", json={"claimant_id": other["id"], "phone": "+13125550100"}, headers=h, timeout=30)
    assert r.status_code == 404


def _seed_otp(mdb, profile, code, minutes):
    mdb.otp_codes.delete_many({"claimant_id": profile["id"]})
    now = datetime.now(timezone.utc)
    mdb.otp_codes.insert_one({
        "claimant_id": profile["id"], "user_id": profile["user_id"], "phone": "+13125550199",
        "code": code, "expires_at": now + timedelta(minutes=minutes), "used": False, "created_at": now,
    })


def test_sms_otp_verify_flow(pro_user, mdb):
    h, profile = pro_user
    _seed_otp(mdb, profile, "424242", minutes=10)
    url = f"{API}/sms/verify-otp"
    assert requests.post(url, json={"claimant_id": profile["id"], "code": "000000"}, headers=h, timeout=30).status_code == 400
    ok = requests.post(url, json={"claimant_id": profile["id"], "code": "424242"}, headers=h, timeout=30)
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"ok": True, "phone": "+13125550199"}
    prof = mdb.profiles.find_one({"id": profile["id"]})
    assert prof["sms_verified"] is True and prof["sms_phone"] == "+13125550199"
    assert requests.post(url, json={"claimant_id": profile["id"], "code": "424242"}, headers=h, timeout=30).status_code == 400


def test_sms_otp_expired(pro_user, mdb):
    h, profile = pro_user
    _seed_otp(mdb, profile, "999999", minutes=-1)
    r = requests.post(f"{API}/sms/verify-otp", json={"claimant_id": profile["id"], "code": "999999"}, headers=h, timeout=30)
    assert r.status_code == 400 and "expired" in r.text.lower()


def test_sms_rate_limit(pro_user, mdb):
    h, profile = pro_user
    phone = "+13125559999"
    mdb.sms_log.delete_many({"phone": phone})
    mdb.sms_log.insert_one({"phone": phone, "claimant_id": "seeded", "body_preview": "seed",
                            "sent_at": datetime.now(timezone.utc) - timedelta(minutes=1)})
    r = requests.post(f"{API}/sms/send-otp", json={"claimant_id": profile["id"], "phone": phone}, headers=h, timeout=30)
    assert r.status_code == 502 and "rate-limited" in r.text.lower()
    assert mdb.sms_log.count_documents({"phone": phone}) == 1
    assert _audit(h, action="OTP_SEND")


# ---------- Mailgun bounce handling ----------
def _signed(event, recipient):
    key = os.environ["MAILGUN_WEBHOOK_SIGNING_KEY"]
    ts, token = str(int(time.time())), uuid.uuid4().hex
    sig = hmac.new(key.encode(), f"{ts}{token}".encode(), hashlib.sha256).hexdigest()
    return {"signature": {"timestamp": ts, "token": token, "signature": sig},
            "data": {"event": event, "recipient": recipient}}


@pytest.mark.skipif(not os.environ.get("MAILGUN_WEBHOOK_SIGNING_KEY"), reason="MAILGUN_WEBHOOK_SIGNING_KEY not configured")
def test_mailgun_bounce_disables_reminders(mdb):
    h, profile = _onboarded(mdb)
    bounce = f"ci-bounce-{uuid.uuid4().hex[:8]}@example.com"
    r = requests.put(f"{API}/profile", json={"label": "Primary", "reminder_email": bounce, "reminders_enabled": True}, headers=h, timeout=30)
    assert r.status_code == 200, r.text

    bad = _signed("email.bounced", bounce)
    bad["signature"]["signature"] = "0" * 64
    assert requests.post(f"{API}/webhooks/mailgun", json=bad, timeout=30).status_code == 403

    w = requests.post(f"{API}/webhooks/mailgun", json=_signed("email.bounced", bounce), timeout=30)
    assert w.status_code == 200 and w.json() == {"ok": True}
    prof = mdb.profiles.find_one({"id": profile["id"]})
    assert prof["reminders_enabled"] is False and prof["email_bounced"] is True
    assert mdb.email_events.find_one({"type": "email.bounced", "to": [bounce]})


@needs_admin
def test_admin_email_events_list(AH):
    r = requests.get(f"{API}/admin/email-events", headers=AH, timeout=30)
    assert r.status_code == 200 and isinstance(r.json(), list)


# ---------- assets ----------
def test_report_assets_present():
    for name in ("ides-logo.png", "ADJ034F.pdf"):
        p = BACKEND_DIR / "assets" / name
        assert p.exists() and p.stat().st_size > 0, f"{name} missing"
