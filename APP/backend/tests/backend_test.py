"""Backend tests for Illinois UI Job Search Tracker."""
import os
import io
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
API = f"{BASE_URL}/api"

# The fake Clerk (tests/clerk_stub.py) that the backend is pointed at in CI.
# It serves the JWKS the backend verifies against, so tokens minted here go
# through the real RS256 signature and issuer checks — nothing is bypassed,
# and there is no test-only branch in the production auth path.
CLERK_STUB = os.environ.get("CLERK_STUB_URL", "http://127.0.0.1:8799").rstrip("/")


@pytest.fixture(scope="session")
def session():
    """A signed session for a fresh Clerk user."""
    email = f"ci-{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(
        f"{CLERK_STUB}/__test__/token",
        json={"email": email, "name": "CI Tester"},
        timeout=30,
    )
    assert r.status_code == 200, f"clerk stub mint failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def token(session):
    return session["token"]


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---- auth ----
# Registration, login, password reset and email verification are Clerk's now
# and have no endpoints here to test. What this file still owns is the
# verification seam: does the backend accept exactly the tokens it should.
def test_auth_me_provisions_user(H, session):
    """First authenticated request should create the local user row.

    Lazy provisioning — there is no webhook, so the user document is written
    on first contact (clerk_auth.get_or_create_user). Must run before the
    profile tests below, which is why it sits first in the file: those create
    the claimant profile and would flip needs_onboarding.
    """
    r = requests.get(f"{API}/auth/me", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == session["email"]
    assert data["role"] == "user"
    assert data["platform_role"] == "user"
    # Clerk sign-up collects no claimant details, so onboarding is pending.
    assert data["needs_onboarding"] is True


def _db():
    """Direct Mongo handle for asserting on fields the API does not expose."""
    from pymongo import MongoClient

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    return MongoClient(url)[os.environ.get("DB_NAME", "ci_test_db")]


def test_provisioning_records_verified_email(H, session):
    """F1: reminders are gated on users.email_verified, so provisioning must set it.

    Runs after test_auth_me_provisions_user, which created the row.
    """
    users = _db().users
    u = users.find_one({"clerk_id": session["clerk_id"]})
    assert u is not None
    assert u["email_verified"] is True
    assert u.get("email_verified_checked_at")

    # An account provisioned before this fix has no email_verified at all.
    # The next authenticated request must heal it from Clerk.
    users.update_one(
        {"clerk_id": session["clerk_id"]},
        {"$unset": {"email_verified": "", "email_verified_checked_at": ""}},
    )
    r = requests.get(f"{API}/auth/me", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    assert users.find_one({"clerk_id": session["clerk_id"]})["email_verified"] is True


def test_provisioning_records_unverified_email():
    """An address Clerk has not verified must not be marked verified."""
    r = requests.post(
        f"{CLERK_STUB}/__test__/token",
        json={
            "email": f"ci-unverified-{uuid.uuid4().hex[:10]}@example.com",
            "email_verified": False,
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    minted = r.json()
    r = requests.get(
        f"{API}/auth/me",
        headers={"Authorization": f"Bearer {minted['token']}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    u = _db().users.find_one({"clerk_id": minted["clerk_id"]})
    assert u["email_verified"] is False


def _mint(email, verified=True):
    r = requests.post(
        f"{CLERK_STUB}/__test__/token",
        json={"email": email, "email_verified": verified},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _me(minted):
    return requests.get(
        f"{API}/auth/me",
        headers={"Authorization": f"Bearer {minted['token']}"},
        timeout=30,
    )


def test_adoption_requires_verified_email():
    """F4: a Clerk account may only take over an existing row by email once
    Clerk has verified that email. The stub gives every mint a new clerk_id,
    so a second mint for the same address exercises the adoption path."""
    email = f"ci-adopt-{uuid.uuid4().hex[:10]}@example.com"
    original = _mint(email)
    r = _me(original)
    assert r.status_code == 200, r.text
    original_id = r.json()["id"]

    # Same email, unverified: refused, and the row is left alone.
    r = _me(_mint(email, verified=False))
    assert r.status_code == 403, r.text
    row = _db().users.find_one({"email": email})
    assert row["clerk_id"] == original["clerk_id"]
    assert _db().users.count_documents({"email": email}) == 1

    # Same email, verified: adopted, same local user id.
    newcomer = _mint(email)
    r = _me(newcomer)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == original_id
    assert _db().users.find_one({"email": email})["clerk_id"] == newcomer["clerk_id"]


def test_auth_me_no_token():
    r = requests.get(f"{API}/auth/me", timeout=30)
    assert r.status_code == 401


def test_auth_me_malformed_token():
    r = requests.get(
        f"{API}/auth/me", headers={"Authorization": "Bearer not.a.jwt"}, timeout=30
    )
    assert r.status_code == 401


def test_auth_me_rejects_foreign_signing_key():
    """A well-formed RS256 token signed by a key the JWKS doesn't publish.

    This is the test that actually matters: it proves the backend verifies
    signatures against Clerk's published keys rather than merely decoding the
    token and trusting its claims.
    """
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rogue.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    now = int(time.time())
    forged = jwt.encode(
        {
            "sub": "user_forged",
            "iss": CLERK_STUB,
            "iat": now,
            "exp": now + 3600,
            "fva": [0, -1],
        },
        pem,
        algorithm="RS256",
        headers={"kid": "ijt-test-key-1"},
    )
    r = requests.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"}, timeout=30
    )
    assert r.status_code == 401, "forged token was accepted"


def test_onboarding_creates_claimant_profile(H):
    body = {
        "first_name": "CI",
        "last_name": "Tester",
        "phone": "(312) 555-0100",
        "sms_opt_in": False,
        "dob": "1990-01-01",
        "address": "100 W Randolph St",
        "city": "Chicago",
        "zip": "60601",
        "knows_next_cert_date": "na",
    }
    r = requests.post(f"{API}/auth/onboarding", json=body, headers=H, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["first_name"] == "CI"

    # Onboarding is idempotent — a double submit must not fork the records.
    again = requests.post(f"{API}/auth/onboarding", json=body, headers=H, timeout=30)
    assert again.status_code == 200
    assert again.json()["id"] == r.json()["id"]

    me = requests.get(f"{API}/auth/me", headers=H, timeout=30)
    assert me.json()["needs_onboarding"] is False


def _paid_user_with_claimant():
    """A fresh user on an active Pro subscription, with one claimant profile.

    Calendar events and document storage are paid features, so the
    ownership checks behind them are only reachable on a paid tier. The
    subscription row is written straight to Mongo; billing is not under test.
    """
    from datetime import datetime, timedelta, timezone

    minted = _mint(f"ci-owner-{uuid.uuid4().hex[:10]}@example.com")
    h = {"Authorization": f"Bearer {minted['token']}"}
    r = requests.post(
        f"{API}/auth/onboarding",
        json={
            "first_name": "Owner", "last_name": "Check", "phone": "(312) 555-0101",
            "sms_opt_in": False, "dob": "1990-01-01", "address": "1 N State St",
            "city": "Chicago", "zip": "60602", "knows_next_cert_date": "na",
        },
        headers=h, timeout=30,
    )
    assert r.status_code == 200, r.text
    profile_id = r.json()["id"]
    user_id = r.json()["user_id"]
    _db().subscriptions.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id, "tier": "pro", "status": "active",
            "current_period_end": datetime.now(timezone.utc) + timedelta(days=30),
        }},
        upsert=True,
    )
    return h, profile_id


def test_calendar_event_rejects_foreign_claimant(H):
    """F2: a calendar event may only reference the caller's own claimant.

    The reminder jobs email the linked profile's reminder_email, so another
    account's profile id here would redirect reminders to that claimant.
    """
    h, own_profile = _paid_user_with_claimant()
    # H belongs to the shared session user; its claimant is someone else's.
    foreign_profile = requests.get(f"{API}/profile", headers=H, timeout=30).json()["id"]
    event = {"event_date": "2030-01-07", "event_type": "other", "title": "x"}

    r = requests.post(f"{API}/calendar-events", json={**event, "claimant_id": foreign_profile}, headers=h, timeout=30)
    assert r.status_code == 404, r.text
    r = requests.post(f"{API}/calendar-events", json={**event, "claimant_id": str(uuid.uuid4())}, headers=h, timeout=30)
    assert r.status_code == 404, r.text

    r = requests.post(f"{API}/calendar-events", json={**event, "claimant_id": own_profile}, headers=h, timeout=30)
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    r = requests.post(f"{API}/calendar-events", json=event, headers=h, timeout=30)
    assert r.status_code == 201, r.text

    # Updates are checked the same way.
    r = requests.put(f"{API}/calendar-events/{eid}", json={**event, "claimant_id": foreign_profile}, headers=h, timeout=30)
    assert r.status_code == 404, r.text
    stored = _db().calendar_events.find_one({"id": eid})
    assert stored["claimant_id"] == own_profile


def test_document_upload_rejects_foreign_claimant(H):
    """F2: document uploads may only be filed under the caller's own claimant."""
    h, _ = _paid_user_with_claimant()
    foreign_profile = requests.get(f"{API}/profile", headers=H, timeout=30).json()["id"]
    r = requests.post(
        f"{API}/documents/upload",
        headers=h,
        data={"title": "x", "claimant_id": foreign_profile},
        files={"file": ("x.pdf", b"%PDF-1.4 not really", "application/pdf")},
        timeout=30,
    )
    assert r.status_code == 404, r.text


# ---- profile ----
def test_profile_upsert(H):
    body = {"first_name": "Demo", "last_name": "Claimant", "middle_initial": "A",
            "claimant_id_last4": "1234", "address": "100 W Randolph St", "city": "Chicago",
            "state": "IL", "zip_code": "60601", "phone": "312-555-0100", "occupation": "Software Developer"}
    r = requests.put(f"{API}/profile", json=body, headers=H, timeout=30)
    assert r.status_code == 200
    g = requests.get(f"{API}/profile", headers=H, timeout=30)
    assert g.status_code == 200
    assert g.json()["first_name"] == "Demo"


# ---- benefit weeks CRUD ----
@pytest.fixture(scope="session")
def week_id(H):
    body = {"week_start": "2026-01-04", "week_end": "2026-01-10", "notes": "TEST_week", "certified": False}
    r = requests.post(f"{API}/benefit-weeks", json=body, headers=H, timeout=30)
    assert r.status_code == 200, r.text
    wid = r.json()["id"]
    yield wid
    requests.delete(f"{API}/benefit-weeks/{wid}", headers=H, timeout=30)


def test_list_weeks(H, week_id):
    r = requests.get(f"{API}/benefit-weeks", headers=H, timeout=30)
    assert r.status_code == 200
    weeks = r.json()
    assert any(w["id"] == week_id for w in weeks)
    assert all("contact_count" in w for w in weeks)


def test_get_week(H, week_id):
    r = requests.get(f"{API}/benefit-weeks/{week_id}", headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json()["notes"] == "TEST_week"


def test_update_week(H, week_id):
    body = {"week_start": "2026-01-04", "week_end": "2026-01-10", "notes": "TEST_updated", "certified": True}
    r = requests.put(f"{API}/benefit-weeks/{week_id}", json=body, headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json()["certified"] is True


# ---- contacts CRUD ----
def test_contact_crud(H, week_id):
    body = {"benefit_week_id": week_id, "contact_date": "2026-01-05", "employer_name": "TEST_Acme",
            "employer_address": "1 Main St", "contact_method": "Online", "type_of_work": "Dev",
            "position_applied": "SE", "person_contacted": "", "result": "Applied", "source_url": ""}
    r = requests.post(f"{API}/contacts", json=body, headers=H, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r = requests.get(f"{API}/contacts?week_id={week_id}", headers=H, timeout=30)
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.json())

    body["result"] = "Interview"
    r = requests.put(f"{API}/contacts/{cid}", json=body, headers=H, timeout=30)
    assert r.status_code == 200 and r.json()["result"] == "Interview"

    r = requests.delete(f"{API}/contacts/{cid}", headers=H, timeout=30)
    assert r.status_code == 200


# ---- CSV import ----
def test_csv_import(H, week_id):
    csv_data = "date,employer,address,method,position,result\n2026-01-06,TEST_CsvCo,123 Loop,Online,Engineer,Applied\n2026-01-07,TEST_CsvCo2,456 St,Email,Analyst,Applied\n"
    files = {"file": ("test.csv", io.StringIO(csv_data).read().encode(), "text/csv")}
    data = {"week_id": week_id}
    r = requests.post(f"{API}/import/csv", headers=H, files=files, data=data, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 2


# ---- screenshot endpoint exists (no real call) ----
def test_screenshot_no_auth():
    r = requests.post(f"{API}/import/screenshot", timeout=30)
    assert r.status_code in (401, 422)


def test_screenshot_bad_week(H):
    files = {"file": ("x.png", b"\x89PNG\r\n", "image/png")}
    data = {"week_id": "non-existent-week-id"}
    r = requests.post(f"{API}/import/screenshot", headers=H, files=files, data=data, timeout=30)
    assert r.status_code == 404


# ---- audit log ----
def test_audit_log(H):
    r = requests.get(f"{API}/audit-log", headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json()
    actions = {it["action"] for it in items}
    # No LOGIN entry: sign-in happens client-side against Clerk and never
    # touches this server, so the audit trail starts at onboarding.
    assert "ONBOARDING" in actions
    assert "CREATE" in actions


# ---- dashboard ----
def test_dashboard(H):
    r = requests.get(f"{API}/dashboard", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ["total_weeks", "total_contacts", "compliant_weeks", "non_compliant_weeks", "profile_complete"]:
        assert k in d


# ---- PDF report ----
def test_pdf_report(H, week_id):
    r = requests.get(f"{API}/reports/benefit-week/{week_id}", headers=H, timeout=60)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


# ---- cascade delete ----
def test_cascade_delete(H):
    body = {"week_start": "2026-02-01", "week_end": "2026-02-07", "notes": "TEST_cascade", "certified": False}
    r = requests.post(f"{API}/benefit-weeks", json=body, headers=H, timeout=30)
    wid = r.json()["id"]
    c = {"benefit_week_id": wid, "contact_date": "2026-02-02", "employer_name": "TEST_X",
         "employer_address": "", "contact_method": "Online", "type_of_work": "", "position_applied": "",
         "person_contacted": "", "result": "Applied", "source_url": ""}
    requests.post(f"{API}/contacts", json=c, headers=H, timeout=30)
    requests.delete(f"{API}/benefit-weeks/{wid}", headers=H, timeout=30)
    r = requests.get(f"{API}/contacts?week_id={wid}", headers=H, timeout=30)
    assert r.status_code == 200 and len(r.json()) == 0