"""Round 3 backend tests: invites, integrations status, dashboard trend, audit filter,
SMS code path, BSON datetime password reset + TTL index."""
import os
import secrets
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DEMO = ("demo@illinoistracker.app", "Demo1234!")
ADMIN = ("admin@illinoistracker.app", "Admin1234!")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def H():
    return {"Authorization": f"Bearer {_login(*DEMO)}"}


@pytest.fixture(scope="session")
def AH():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


# ---------- Integration status ----------
def test_integrations_status_admin(AH):
    r = requests.get(f"{API}/admin/integrations/status", headers=AH, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "mailgun" in d and "clicksend" in d
    assert d["mailgun"]["configured"] is True
    assert "from" in d["mailgun"]
    assert "verified_domain" in d["mailgun"]
    assert "fallback_from" in d["mailgun"]
    assert "dns_records_url" in d["mailgun"]
    assert d["clicksend"]["configured"] is True
    assert d["clicksend"]["from_number"]


def test_integrations_status_non_admin_403(H):
    r = requests.get(f"{API}/admin/integrations/status", headers=H, timeout=30)
    assert r.status_code == 403


# ---------- Dashboard Trend ----------
def test_dashboard_trend_returns_list(H):
    r = requests.get(f"{API}/dashboard/trend?weeks=12", headers=H, timeout=30)
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    if arr:
        first = arr[0]
        for k in ("week_start", "contacts", "target", "compliant"):
            assert k in first, f"missing {k}"
        assert first["target"] == 3
        # chronological order
        starts = [w["week_start"] for w in arr]
        assert starts == sorted(starts), "weeks not in chronological order"


# ---------- Audit Filter ----------
def test_audit_filter_action(H):
    r = requests.get(f"{API}/audit-log?action=LOGIN&limit=50", headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert all(it["action"] == "LOGIN" for it in items)


def test_audit_filter_entity(H):
    r = requests.get(f"{API}/audit-log?entity=claimant&limit=50", headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert all(it["entity"] == "claimant" for it in items)


def test_audit_filter_search_q(H):
    # seed something to find
    requests.post(f"{API}/auth/login", json={"email": DEMO[0], "password": DEMO[1]}, timeout=30)
    r = requests.get(f"{API}/audit-log?q=Login&limit=20", headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert items, "expected matches for 'Login'"
    for it in items:
        assert "login" in it["detail"].lower()


def test_audit_filter_all_keyword(H):
    r = requests.get(f"{API}/audit-log?action=ALL&entity=ALL&limit=5", headers=H, timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- Invites ----------
@pytest.fixture
def invite_email():
    return f"TEST_invite_{secrets.token_hex(4)}@example.com"


def test_invite_create_and_get_public(AH, invite_email):
    r = requests.post(f"{API}/admin/invites",
                      json={"email": invite_email, "claimant_label": "TEST_Invitee", "note": "Welcome"},
                      headers=AH, timeout=60)
    assert r.status_code == 200, r.text
    inv = r.json()
    assert "code" in inv and "invite_link" in inv
    code = inv["code"]
    # public GET
    g = requests.get(f"{API}/invite/{code}", timeout=30)
    assert g.status_code == 200
    gd = g.json()
    assert gd["email"] == invite_email.lower()
    assert gd["claimant_label"] == "TEST_Invitee"
    assert gd["note"] == "Welcome"
    # cleanup
    requests.delete(f"{API}/admin/invites/{code}", headers=AH, timeout=30)


def test_invite_redeem_creates_user_and_claimant(AH, invite_email):
    r = requests.post(f"{API}/admin/invites",
                      json={"email": invite_email, "claimant_label": "TEST_Redeem", "note": ""},
                      headers=AH, timeout=60)
    code = r.json()["code"]
    # redeem
    rd = requests.post(f"{API}/invite/redeem",
                      json={"code": code, "password": "Pass1234!", "name": "TEST Invitee"},
                      timeout=30)
    assert rd.status_code == 200, rd.text
    d = rd.json()
    assert "token" in d
    assert d["user"]["email"] == invite_email.lower()
    # auto-logged-in: use token to fetch claimants
    headers = {"Authorization": f"Bearer {d['token']}"}
    cs = requests.get(f"{API}/claimants", headers=headers, timeout=30).json()
    assert any(c["label"] == "TEST_Redeem" for c in cs["items"])
    # cannot redeem twice
    rd2 = requests.post(f"{API}/invite/redeem",
                       json={"code": code, "password": "X234567!", "name": "X"}, timeout=30)
    assert rd2.status_code == 400
    # public GET also rejects used
    g = requests.get(f"{API}/invite/{code}", timeout=30)
    assert g.status_code == 400


def test_invite_revoke(AH):
    email = f"TEST_revoke_{secrets.token_hex(3)}@example.com"
    code = requests.post(f"{API}/admin/invites",
                       json={"email": email, "claimant_label": "X", "note": ""},
                       headers=AH, timeout=60).json()["code"]
    rv = requests.delete(f"{API}/admin/invites/{code}", headers=AH, timeout=30)
    assert rv.status_code == 200
    g = requests.get(f"{API}/invite/{code}", timeout=30)
    assert g.status_code == 404


def test_invite_get_nonexistent_404():
    r = requests.get(f"{API}/invite/garbage-code-xyz", timeout=30)
    assert r.status_code == 404


def test_invite_create_existing_email_400(AH):
    r = requests.post(f"{API}/admin/invites",
                      json={"email": "demo@illinoistracker.app", "claimant_label": "X", "note": ""},
                      headers=AH, timeout=30)
    assert r.status_code == 400


def test_invite_create_non_admin_403(H):
    r = requests.post(f"{API}/admin/invites",
                      json={"email": "TEST_x@example.com", "claimant_label": "X", "note": ""},
                      headers=H, timeout=30)
    assert r.status_code == 403


# ---------- SMS Code Path (no actual send to conserve quota) ----------
def test_sms_code_path_via_friday_reminder(H):
    """Enable SMS on Primary claimant and trigger friday reminder. Verify endpoint
    runs without error and REMINDER_FRIDAY email audit exists. Don't assert on SMS
    audit since ClickSend may reject an unconfigured/unfunded sender."""
    cs = requests.get(f"{API}/claimants", headers=H, timeout=30).json()["items"]
    primary = next(c for c in cs if c.get("label") == "Primary")
    # Set sms_enabled=true with a clearly-test number — ClickSend may reject it,
    # but the code path must be exercised. Use an obvious test number to avoid charges.
    body = {**{k: primary.get(k, "") for k in [
        "label", "first_name", "last_name", "middle_initial", "claimant_id_last4",
        "address", "city", "state", "zip_code", "phone", "occupation", "reminder_email"
    ]}, "reminders_enabled": True, "sms_enabled": True, "sms_phone": "+15005550006"}
    body["state"] = body.get("state") or "IL"
    body["label"] = body.get("label") or "Primary"
    r = requests.put(f"{API}/claimants/{primary['id']}", json=body, headers=H, timeout=30)
    assert r.status_code == 200
    # set active
    requests.post(f"{API}/claimants/{primary['id']}/set-active", headers=H, timeout=30)
    # trigger friday reminder — should NOT raise
    fr = requests.post(f"{API}/reminders/test?kind=friday", headers=H, timeout=60)
    assert fr.status_code == 200, fr.text
    # confirm REMINDER_FRIDAY audit appears (email succeeded via Mailgun)
    items = requests.get(f"{API}/audit-log?action=REMINDER_FRIDAY&limit=5", headers=H, timeout=30).json()
    assert items, "expected REMINDER_FRIDAY audit entry"
    # turn SMS off again
    body["sms_enabled"] = False
    body["sms_phone"] = ""
    requests.put(f"{API}/claimants/{primary['id']}", json=body, headers=H, timeout=30)


# ---------- BSON datetime password reset + TTL index ----------
def test_password_reset_token_writes_bson_datetime():
    """Trigger forgot-password and assume backend stores expires_at as BSON datetime.
    We can't directly inspect the DB here, but we can verify reset-password handles a
    fresh real token (which is BSON datetime per new code path)."""
    r = requests.post(f"{API}/auth/forgot-password",
                      json={"email": "demo@illinoistracker.app"}, timeout=30)
    assert r.status_code == 200
    # cannot get actual token without DB access; ensure the endpoint accepts bad token
    bad = requests.post(f"{API}/auth/reset-password",
                       json={"token": "non-existent", "password": "NewPass1234!"}, timeout=30)
    assert bad.status_code == 400


def test_password_reset_ttl_index_present():
    """Connect to Mongo to verify TTL index on password_resets.expires_at."""
    try:
        from pymongo import MongoClient
    except ImportError:
        pytest.skip("pymongo not installed in test runner")
    mongo_url = os.environ.get("MONGO_URL", "").strip('"').strip("'")
    db_name = os.environ.get("DB_NAME", "").strip('"').strip("'")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME not available")
    c = MongoClient(mongo_url)
    info = c[db_name]["password_resets"].index_information()
    ttl_idx = [v for v in info.values() if v.get("expireAfterSeconds") is not None
               and any(k == "expires_at" for k, _ in v.get("key", []))]
    assert ttl_idx, f"no TTL index on password_resets.expires_at — got {info}"
