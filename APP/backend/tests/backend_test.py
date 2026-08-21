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