"""Week 2 hardening tests: production boot checks, azp, regex, webhooks, headers.

Runs alongside backend_test.py in CI, against the same running backend and
Clerk stub. The boot checks run in a subprocess so each one gets its own
environment without touching the backend under test.
"""
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path(__file__).resolve().parent.parent
# The in-process tests import clerk_auth and core directly.
sys.path.insert(0, str(BACKEND_DIR))
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
API = f"{BASE_URL}/api"
CLERK_STUB = os.environ.get("CLERK_STUB_URL", "http://127.0.0.1:8799").rstrip("/")


def _mint(email=None):
    r = requests.post(
        f"{CLERK_STUB}/__test__/token",
        json={"email": email or f"ci-hard-{uuid.uuid4().hex[:10]}@example.com"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _import_in(env_overrides, module):
    """Import `module` in a fresh interpreter with the given env changes."""
    env = {**os.environ, **env_overrides}
    for k, v in list(env.items()):
        if v is None:
            env.pop(k)
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60,
    )


# ---- H1 / H2: production refuses to boot misconfigured ----
def test_production_requires_authorized_parties():
    r = _import_in({"APP_ENV": "production", "CLERK_AUTHORIZED_PARTIES": None}, "clerk_auth")
    assert r.returncode != 0
    assert "CLERK_AUTHORIZED_PARTIES is required in production" in r.stderr


def test_production_rejects_wildcard_cors():
    r = _import_in(
        {"APP_ENV": "production", "CLERK_AUTHORIZED_PARTIES": "https://app.example", "CORS_ORIGINS": "*"},
        "core",
    )
    assert r.returncode != 0
    assert "CORS_ORIGINS must list explicit origins in production" in r.stderr


def test_unset_app_env_means_production():
    r = _import_in({"APP_ENV": None, "CLERK_AUTHORIZED_PARTIES": None}, "clerk_auth")
    assert r.returncode != 0, "a missing APP_ENV must get the strict production checks"


def test_production_boots_when_configured():
    r = _import_in(
        {
            "APP_ENV": "production",
            "CLERK_AUTHORIZED_PARTIES": "https://app.example",
            "CORS_ORIGINS": "https://app.example",
        },
        "core",
    )
    assert r.returncode == 0, r.stderr


# ---- H2: tokens without the right azp are rejected when parties are pinned ----
def test_azp_pinning(monkeypatch):
    import clerk_auth
    from fastapi import HTTPException

    token = _mint()["token"]  # stub tokens carry no azp
    monkeypatch.setattr(clerk_auth, "CLERK_AUTHORIZED_PARTIES", ["https://app.example"])
    with pytest.raises(HTTPException) as exc:
        clerk_auth.verify_session_token(token)
    assert exc.value.status_code == 401

    monkeypatch.setattr(clerk_auth, "CLERK_AUTHORIZED_PARTIES", [])
    assert clerk_auth.verify_session_token(token)["sub"]


# ---- H3: user text in a $regex is escaped ----
def test_audit_search_tolerates_regex_metacharacters():
    h = {"Authorization": f"Bearer {_mint()['token']}"}
    for q in ["(", "[a-", "(a+)+$", "*"]:
        r = requests.get(f"{API}/audit-log", params={"q": q}, headers=h, timeout=30)
        assert r.status_code == 200, f"q={q!r}: {r.status_code} {r.text}"


# ---- H4: Mailgun webhook replay window ----
def _mailgun_post(timestamp):
    return requests.post(
        f"{API}/webhooks/mailgun",
        json={"signature": {"timestamp": timestamp, "token": uuid.uuid4().hex, "signature": "0" * 64}},
        timeout=30,
    )


def test_mailgun_webhook_rejects_old_timestamp():
    r = _mailgun_post(str(int(time.time()) - 3600))
    assert r.status_code == 403, r.text
    assert "too old" in r.text


def test_mailgun_webhook_rejects_bad_timestamp():
    r = _mailgun_post("not-a-number")
    assert r.status_code == 400, r.text


# ---- H6: download filenames are sanitized and quoted ----
def test_content_disposition_sanitizes():
    import core

    assert core.content_disposition("inline", "report.pdf") == 'inline; filename="report.pdf"'
    hostile = core.content_disposition("attachment", 'a"b\r\nSet-Cookie: x=1.csv')
    assert "\r" not in hostile and "\n" not in hostile
    assert hostile.count('"') == 2
    assert core.content_disposition("inline", "", "document") == 'inline; filename="document"'
