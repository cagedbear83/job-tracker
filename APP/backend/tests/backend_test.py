"""Backend tests for Illinois UI Job Search Tracker."""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-search-hub-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
DEMO_EMAIL = "demo@illinoistracker.app"
DEMO_PASSWORD = "Demo1234!"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    return data["token"]


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---- auth ----
def test_register_duplicate_or_new():
    # first_name/last_name/phone/dob/address/city/zip are required as of the
    # Aug 20 Register-page work (core.py's RegisterIn) — a request missing
    # any of them now gets a 422 instead of reaching the duplicate-email
    # check, so this payload needs all of them filled in to still exercise
    # the duplicate-vs-new-email path this test is actually about.
    r = requests.post(f"{API}/auth/register", json={
        "email": "TEST_user1@example.com", "password": "Lake Sunrise Coffee 42!", "name": "T",
        "first_name": "Test", "last_name": "User", "phone": "3125550100", "dob": "1990-01-01",
        "address": "123 Main St", "city": "Chicago", "zip": "60601",
    }, timeout=30)
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        d = r.json()
        assert d["user"]["email"] == "test_user1@example.com"


def test_login_invalid():
    r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"}, timeout=30)
    assert r.status_code == 401


def test_auth_me(H):
    r = requests.get(f"{API}/auth/me", headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json()["email"] == DEMO_EMAIL


def test_auth_me_no_token():
    r = requests.get(f"{API}/auth/me", timeout=30)
    assert r.status_code == 401


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
    assert "LOGIN" in actions
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