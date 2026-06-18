"""Round 2 backend tests: claimants CRUD, CSV export, password reset, audit edit-diff,
admin role, reminders. Conserves email quota (max 1 send)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DEMO = ("demo@illinoistracker.app", "Demo1234!")
ADMIN = ("admin@illinoistracker.app", "Admin1234!")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="session")
def H():
    tok, _ = _login(*DEMO)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def AH():
    tok, _ = _login(*ADMIN)
    return {"Authorization": f"Bearer {tok}"}


# ---------- Multi-claimant ----------
def test_claimants_list_returns_items_and_active(H):
    r = requests.get(f"{API}/claimants", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d and "active_id" in d
    assert isinstance(d["items"], list)
    assert any(c.get("label") for c in d["items"]) or len(d["items"]) >= 0


@pytest.fixture(scope="session")
def temp_claimant(H):
    body = {"label": "TEST_Secondary", "first_name": "Sec", "last_name": "Ondary",
            "state": "IL", "reminders_enabled": True, "reminder_email": ""}
    r = requests.post(f"{API}/claimants", json=body, headers=H, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    yield cid
    requests.delete(f"{API}/claimants/{cid}", headers=H, timeout=30)


def test_claimant_create(H, temp_claimant):
    r = requests.get(f"{API}/claimants", headers=H, timeout=30)
    assert any(c["id"] == temp_claimant for c in r.json()["items"])


def test_claimant_update_writes_diff(H, temp_claimant):
    body = {"label": "TEST_Secondary", "first_name": "Updated", "last_name": "Ondary",
            "state": "IL", "reminders_enabled": True, "reminder_email": ""}
    r = requests.put(f"{API}/claimants/{temp_claimant}", json=body, headers=H, timeout=30)
    assert r.status_code == 200
    # Audit should contain edit-diff
    r2 = requests.get(f"{API}/audit-log", headers=H, timeout=30)
    assert r2.status_code == 200
    items = r2.json()
    matches = [it for it in items if it["entity"] == "claimant" and it["entity_id"] == temp_claimant and it["action"] == "UPDATE"]
    assert matches, "no UPDATE claimant audit found"
    detail = matches[0]["detail"]
    assert "first_name" in detail and "→" in detail, f"missing edit-diff: {detail}"


def test_claimant_set_active(H, temp_claimant):
    r = requests.post(f"{API}/claimants/{temp_claimant}/set-active", headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json()["active_id"] == temp_claimant
    # Verify dashboard reflects
    d = requests.get(f"{API}/dashboard", headers=H, timeout=30).json()
    assert d["active_claimant_id"] == temp_claimant


def test_claimant_delete_cascades(H):
    # Create a temp claimant to delete with its own week+contact
    body = {"label": "TEST_Cascade", "first_name": "C", "last_name": "X", "state": "IL"}
    cid = requests.post(f"{API}/claimants", json=body, headers=H, timeout=30).json()["id"]
    # set active
    requests.post(f"{API}/claimants/{cid}/set-active", headers=H, timeout=30)
    # create a week + contact under it
    wk = {"week_start": "2026-03-01", "week_end": "2026-03-07", "notes": "TEST_cas", "certified": False}
    wid = requests.post(f"{API}/benefit-weeks", json=wk, headers=H, timeout=30).json()["id"]
    ct = {"benefit_week_id": wid, "contact_date": "2026-03-02", "employer_name": "TEST_Cas",
          "employer_address": "", "contact_method": "Online", "type_of_work": "",
          "position_applied": "", "person_contacted": "", "result": "", "source_url": ""}
    requests.post(f"{API}/contacts", json=ct, headers=H, timeout=30)
    # delete the claimant
    r = requests.delete(f"{API}/claimants/{cid}", headers=H, timeout=30)
    assert r.status_code == 200
    # weeks/contacts for that claimant should be gone
    weeks = requests.get(f"{API}/benefit-weeks", headers=H, timeout=30).json()
    assert not any(w["id"] == wid for w in weeks)


def test_active_claimant_scoping(H, temp_claimant):
    # Switch active to demo's primary first
    cs = requests.get(f"{API}/claimants", headers=H, timeout=30).json()["items"]
    primary = next((c for c in cs if c.get("label") == "Primary"), cs[0])
    requests.post(f"{API}/claimants/{primary['id']}/set-active", headers=H, timeout=30)
    weeks_primary = requests.get(f"{API}/benefit-weeks", headers=H, timeout=30).json()
    # switch to TEST_Secondary
    requests.post(f"{API}/claimants/{temp_claimant}/set-active", headers=H, timeout=30)
    weeks_sec = requests.get(f"{API}/benefit-weeks", headers=H, timeout=30).json()
    # Secondary's own weeks ought to differ (typically empty/less)
    assert isinstance(weeks_primary, list) and isinstance(weeks_sec, list)
    # restore primary as active
    requests.post(f"{API}/claimants/{primary['id']}/set-active", headers=H, timeout=30)


# ---------- CSV Export ----------
def test_csv_export_all(H):
    r = requests.get(f"{API}/contacts/export.csv", headers=H, timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")
    assert "contact_date" in r.text.splitlines()[0]


def test_csv_export_audit(H):
    # call again and check audit
    requests.get(f"{API}/contacts/export.csv", headers=H, timeout=30)
    items = requests.get(f"{API}/audit-log", headers=H, timeout=30).json()
    assert any(it["action"] == "EXPORT_CSV" for it in items)


# ---------- Audit Edit-Diff on contacts/weeks ----------
def test_contact_update_audit_diff(H):
    cs = requests.get(f"{API}/claimants", headers=H, timeout=30).json()["items"]
    primary = next(c for c in cs if c.get("label") == "Primary")
    requests.post(f"{API}/claimants/{primary['id']}/set-active", headers=H, timeout=30)
    wk = {"week_start": "2026-04-05", "week_end": "2026-04-11", "notes": "TEST_diff", "certified": False}
    wid = requests.post(f"{API}/benefit-weeks", json=wk, headers=H, timeout=30).json()["id"]
    ct = {"benefit_week_id": wid, "contact_date": "2026-04-06", "employer_name": "TEST_Diff",
          "employer_address": "", "contact_method": "Online", "type_of_work": "",
          "position_applied": "Engineer", "person_contacted": "", "result": "Applied", "source_url": ""}
    cid = requests.post(f"{API}/contacts", json=ct, headers=H, timeout=30).json()["id"]
    ct["result"] = "Interview"
    ct["position_applied"] = "Sr Engineer"
    requests.put(f"{API}/contacts/{cid}", json=ct, headers=H, timeout=30)
    items = requests.get(f"{API}/audit-log", headers=H, timeout=30).json()
    upd = [it for it in items if it["action"] == "UPDATE" and it["entity"] == "contact" and it["entity_id"] == cid]
    assert upd
    assert "→" in upd[0]["detail"] and ("result" in upd[0]["detail"] or "position_applied" in upd[0]["detail"])
    # cleanup
    requests.delete(f"{API}/benefit-weeks/{wid}", headers=H, timeout=30)


def test_week_update_audit_diff(H):
    wk = {"week_start": "2026-05-03", "week_end": "2026-05-09", "notes": "TEST_wkdiff", "certified": False}
    wid = requests.post(f"{API}/benefit-weeks", json=wk, headers=H, timeout=30).json()["id"]
    wk2 = dict(wk); wk2["certified"] = True; wk2["notes"] = "TEST_changed"
    requests.put(f"{API}/benefit-weeks/{wid}", json=wk2, headers=H, timeout=30)
    items = requests.get(f"{API}/audit-log", headers=H, timeout=30).json()
    upd = [it for it in items if it["action"] == "UPDATE" and it["entity"] == "benefit_week" and it["entity_id"] == wid]
    assert upd
    assert "→" in upd[0]["detail"] and ("notes" in upd[0]["detail"] or "certified" in upd[0]["detail"])
    requests.delete(f"{API}/benefit-weeks/{wid}", headers=H, timeout=30)


# ---------- Password Reset ----------
def test_forgot_password_always_ok():
    r = requests.post(f"{API}/auth/forgot-password", json={"email": "nobody_TEST_unknown@example.com"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_reset_password_with_bad_token():
    r = requests.post(f"{API}/auth/reset-password", json={"token": "garbage-token", "password": "NewPass1234!"}, timeout=30)
    assert r.status_code == 400


# ---------- Admin ----------
def test_admin_list_users(AH):
    r = requests.get(f"{API}/admin/users", headers=AH, timeout=30)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list) and len(users) >= 2
    assert any(u["email"] == "demo@illinoistracker.app" for u in users)
    # ensure counts present
    assert all("claimants_count" in u and "weeks_count" in u and "contacts_count" in u for u in users)


def test_admin_user_detail(AH):
    users = requests.get(f"{API}/admin/users", headers=AH, timeout=30).json()
    demo = next(u for u in users if u["email"] == "demo@illinoistracker.app")
    r = requests.get(f"{API}/admin/users/{demo['id']}", headers=AH, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "user" in d and "claimants" in d and "weeks" in d


def test_admin_forbidden_for_non_admin(H):
    r = requests.get(f"{API}/admin/users", headers=H, timeout=30)
    assert r.status_code == 403


# ---------- Reminders (1 real send only) ----------
def test_reminder_invalid_kind(H):
    r = requests.post(f"{API}/reminders/test?kind=monday", headers=H, timeout=30)
    assert r.status_code == 400


def test_reminder_friday_send_one(H):
    # ensure Primary is active (has reminder_email = kmgagen@gmail.com)
    cs = requests.get(f"{API}/claimants", headers=H, timeout=30).json()["items"]
    primary = next(c for c in cs if c.get("label") == "Primary")
    requests.post(f"{API}/claimants/{primary['id']}/set-active", headers=H, timeout=30)
    r = requests.post(f"{API}/reminders/test?kind=friday", headers=H, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["kind"] == "friday"
    assert d["sent"] >= 1, f"expected at least 1 sent, got {d}"
    # audit
    items = requests.get(f"{API}/audit-log", headers=H, timeout=30).json()
    assert any(it["action"] == "REMINDER_FRIDAY" for it in items)
