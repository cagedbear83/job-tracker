"""
Clerk-backed authentication.

This module replaces the hand-rolled session layer that used to live in
core.py (create_token / create_refresh_token / rotate_refresh_token / the
httpOnly refresh cookie / bcrypt password hashing / login_attempts lockout).
Clerk now owns identity: sign-up, sign-in, email verification, password
reset, MFA, and the Google / Apple social providers.

WHAT THIS MODULE DOES NOT OWN — deliberately:

    authorization.  `role` ("user" | "admin") and `platform_role`
    ("user" | "support_staff" | "platform_admin") stay in Mongo and stay the
    backend's decision. Clerk tells us *who* the caller is; this codebase
    decides *what they may do*. That keeps rbac.py, require_admin, and every
    admin router working untouched, and means a compromised or misconfigured
    Clerk instance cannot grant anyone platform admin.

THE SEAM: core.get_current_user() delegates here. Every router depends on
that one function, so swapping its innards migrates the whole API at once.
The Mongo user doc keeps its uuid `id` field as the primary key — all 20
routers reference user["id"] — and gains a `clerk_id` that maps it to Clerk.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import jwt
import requests
from fastapi import HTTPException, Request
from jwt import PyJWKClient

# ── Configuration ────────────────────────────────────────────────────────
# CLERK_ISSUER is the Frontend API origin, e.g.
#   https://your-app-12.clerk.accounts.dev      (development)
#   https://clerk.yourdomain.com                (production, after DNS setup)
# It is the `iss` claim on every Clerk session token.
CLERK_ISSUER = (os.environ.get("CLERK_ISSUER") or "").rstrip("/")
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY")
CLERK_API_BASE = os.environ.get("CLERK_API_BASE", "https://api.clerk.com/v1")

# Optional hardening: Clerk puts the requesting origin in `azp`. Pinning it
# stops a token minted for some other site on the same Clerk instance from
# being replayed here. Comma-separated; empty disables the check.
CLERK_AUTHORIZED_PARTIES = [
    p.strip()
    for p in (os.environ.get("CLERK_AUTHORIZED_PARTIES") or "").split(",")
    if p.strip()
]

# Emails granted admin on first sign-in. This replaces the old
# ADMIN_EMAIL/ADMIN_PASSWORD startup seed, which inserted a Mongo row with a
# bcrypt hash — unreachable now that there is no local password check.
#
# Deliberately an allowlist of *emails*, not a Clerk role: authorization stays
# this database's decision, so nothing configured in the Clerk dashboard can
# hand someone platform admin here.
ADMIN_EMAILS = {
    e.strip().lower()
    for e in (os.environ.get("ADMIN_EMAILS") or "").split(",")
    if e.strip()
}

if not CLERK_ISSUER:
    raise RuntimeError(
        "CLERK_ISSUER environment variable is required "
        "(your Clerk Frontend API URL, e.g. https://xxx.clerk.accounts.dev)"
    )
if not CLERK_ISSUER.startswith(("http://", "https://")):
    # Caught here rather than at first request: without a scheme the JWKS URL
    # is malformed, and the only symptom would be every authenticated request
    # returning a vague "Could not verify session".
    raise RuntimeError(
        "CLERK_ISSUER must include the scheme. "
        f"Got {CLERK_ISSUER!r}; expected something like "
        f"https://{CLERK_ISSUER}"
    )
if not CLERK_SECRET_KEY:
    raise RuntimeError("CLERK_SECRET_KEY environment variable is required")


# ── Token verification ───────────────────────────────────────────────────
JWKS_URL = f"{CLERK_ISSUER}/.well-known/jwks.json"

# PyJWKClient fetches and caches Clerk's public signing keys. Cached across
# requests so this is one network call per key rotation, not per request.
_jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)


def validate_config(timeout: float = 10.0) -> dict:
    """Prove the Clerk configuration works, at boot rather than at first login.

    Fetches the JWKS exactly once. A wrong CLERK_ISSUER is the single most
    likely misconfiguration here — it is easy to paste the Backend API URL, a
    bare host with no scheme, or a development issuer into production — and
    every one of those failure modes otherwise shows up only as a blanket 401
    on every authenticated request, with nothing in the logs naming the cause.

    Raises RuntimeError naming the exact URL tried. Called from the startup
    hook in server.py, so the process refuses to come up misconfigured instead
    of serving a site where nobody can sign in.
    """
    hint = (
        f"CLERK_ISSUER is currently {CLERK_ISSUER!r}.\n"
        "It must be the Frontend API URL from the Clerk dashboard (API Keys) "
        "— NOT the Backend API URL (https://api.clerk.com).\n"
        "  development: https://<slug>.clerk.accounts.dev\n"
        "  production:  https://clerk.<your-domain>"
    )

    try:
        resp = requests.get(JWKS_URL, timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError(
            f"Clerk config invalid: could not reach {JWKS_URL}\n{e}\n\n{hint}"
        ) from e

    if resp.status_code != 200:
        raise RuntimeError(
            f"Clerk config invalid: {JWKS_URL} returned HTTP "
            f"{resp.status_code}.\n\n{hint}"
        )

    try:
        payload = resp.json()
    except ValueError as e:
        # Almost always an HTML error page, i.e. the host is not a Clerk
        # Frontend API at all.
        raise RuntimeError(
            f"Clerk config invalid: {JWKS_URL} did not return JSON (got "
            f"{resp.headers.get('content-type', 'unknown')}).\n\n{hint}"
        ) from e

    keys = payload.get("keys")
    if not isinstance(keys, list) or not keys:
        raise RuntimeError(
            f"Clerk config invalid: {JWKS_URL} returned no signing keys.\n\n{hint}"
        )

    # Not fatal, but a dev issuer with a live secret key (or vice versa) means
    # token verification and the Backend API point at different Clerk
    # instances — worth saying out loud while the logs are still being read.
    # Only the unambiguous direction is worth flagging. A .clerk.accounts.dev
    # issuer is definitely a development instance, so pairing it with a live
    # secret key is definitely wrong. The reverse does NOT hold — a custom
    # domain on a development instance is perfectly normal, so "issuer is not
    # *.clerk.accounts.dev" tells us nothing about which key belongs with it.
    mismatch = None
    if ".clerk.accounts.dev" in CLERK_ISSUER and CLERK_SECRET_KEY.startswith(
        "sk_live_"
    ):
        mismatch = (
            "CLERK_ISSUER is a development instance (.clerk.accounts.dev) but "
            "CLERK_SECRET_KEY is a live key (sk_live_) — token verification and "
            "the Clerk Backend API are pointed at different instances"
        )

    return {
        "jwks_url": JWKS_URL,
        "key_count": len(keys),
        "admin_emails": len(ADMIN_EMAILS),
        "mismatch": mismatch,
    }


def verify_session_token(token: str) -> dict:
    """Verify a Clerk session JWT and return its claims.

    Raises HTTPException(401) on anything suspect. Signature, expiry and
    issuer are all checked; `azp` is checked only when the operator has
    pinned an allowlist.
    """
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            # Clerk session tokens carry no `aud` by default.
            options={"verify_aud": False, "require": ["exp", "iat", "sub"]},
            leeway=10,  # small clock-skew tolerance
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception:
        # JWKS fetch failure, unknown kid, malformed key, etc. Deliberately
        # opaque to the caller — the detail belongs in logs, not a response.
        raise HTTPException(status_code=401, detail="Could not verify session")

    if CLERK_AUTHORIZED_PARTIES:
        azp = claims.get("azp")
        if azp and azp not in CLERK_AUTHORIZED_PARTIES:
            raise HTTPException(status_code=401, detail="Invalid token audience")

    return claims


def extract_token(request: Request) -> Optional[str]:
    """Pull the session token from the Authorization header.

    Header only. The old cookie fallback is gone on purpose: Clerk tokens are
    short-lived and fetched per-request by the client, and accepting them from
    a cookie would reintroduce the CSRF surface the header approach avoids.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] or None
    return None


# ── Clerk Backend API ────────────────────────────────────────────────────
def _clerk_request(method: str, path: str, **kwargs) -> dict:
    """Call the Clerk Backend API with the secret key."""
    resp = requests.request(
        method,
        f"{CLERK_API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {CLERK_SECRET_KEY}",
            "Content-Type": "application/json",
        },
        timeout=15,
        **kwargs,
    )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Clerk API error ({resp.status_code}): {resp.text[:300]}",
        )
    return resp.json() if resp.content else {}


def fetch_clerk_user(clerk_user_id: str) -> dict:
    """Fetch a user record from Clerk.

    Called only when provisioning a user we have not seen before, so this is
    one API call per new account rather than per request. The session token
    itself carries no email or name unless you add them via a custom claim,
    and relying on dashboard-side JWT template config would make provisioning
    silently depend on a setting that is easy to forget.
    """
    return _clerk_request("GET", f"/users/{clerk_user_id}")


def _primary_email(clerk_user: dict) -> str:
    """Best-effort primary email address off a Clerk user record."""
    primary_id = clerk_user.get("primary_email_address_id")
    for addr in clerk_user.get("email_addresses") or []:
        if addr.get("id") == primary_id:
            return (addr.get("email_address") or "").lower()
    addrs = clerk_user.get("email_addresses") or []
    if addrs:
        return (addrs[0].get("email_address") or "").lower()
    return ""


def _display_name(clerk_user: dict, fallback_email: str) -> str:
    first = (clerk_user.get("first_name") or "").strip()
    last = (clerk_user.get("last_name") or "").strip()
    name = " ".join(p for p in (first, last) if p)
    if name:
        return name
    username = (clerk_user.get("username") or "").strip()
    if username:
        return username
    return fallback_email.split("@")[0] or "New user"


# ── Provisioning ─────────────────────────────────────────────────────────
async def get_or_create_user(db, claims: dict) -> dict:
    """Map a verified Clerk session to this app's Mongo user document.

    Lazy provisioning: the first authenticated request from a new Clerk
    account creates the local user doc. There is no webhook to miss, and a
    user created out-of-band (Clerk dashboard, an invitation accepted while
    the webhook endpoint was down) still works on their next request.

    Note this creates the `users` doc only. The claimant `profiles` doc is
    created later, by the onboarding step, via the existing upserting
    PUT /api/profile — registration used to write both at once, but Clerk
    sign-up collects only an email and password.
    """
    clerk_id = claims["sub"]

    user = await db.users.find_one({"clerk_id": clerk_id}, {"_id": 0, "password_hash": 0})
    if user:
        return user

    clerk_user = fetch_clerk_user(clerk_id)
    email = _primary_email(clerk_user)

    # An account may already exist from before the Clerk migration, or from an
    # invitation that pre-seeded a record. Adopt it by email rather than
    # creating a duplicate that would orphan their profiles and benefit weeks.
    if email:
        existing = await db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            updates = {"clerk_id": clerk_id}
            # Bootstrap admin on adoption too, so listing an email in
            # ADMIN_EMAILS works whether or not the row predates Clerk.
            if email in ADMIN_EMAILS and existing.get("role") != "admin":
                updates["role"] = "admin"
                updates["platform_role"] = "platform_admin"
            await db.users.update_one(
                {"id": existing["id"]},
                {"$set": updates, "$unset": {"password_hash": ""}},
            )
            existing.pop("password_hash", None)
            existing.update(updates)
            return existing

    now = datetime.now(timezone.utc).isoformat()
    is_admin = bool(email) and email in ADMIN_EMAILS
    user_doc = {
        "id": str(uuid.uuid4()),  # stays the primary key every router uses
        "clerk_id": clerk_id,
        "email": email,
        "name": _display_name(clerk_user, email),
        # Authorization defaults live here, not in Clerk. Elevating someone is
        # a deliberate act against this database (or the ADMIN_EMAILS bootstrap).
        "role": "admin" if is_admin else "user",
        "platform_role": "platform_admin" if is_admin else "user",
        "created_at": now,
    }

    # Invitation metadata, if this account came in through one. Clerk copies
    # public_metadata from the invitation onto the user it creates.
    meta = clerk_user.get("public_metadata") or {}
    if meta.get("invited_by"):
        user_doc["invited_by"] = meta["invited_by"]
    if meta.get("claimant_label"):
        user_doc["pending_claimant_label"] = meta["claimant_label"]

    await db.users.insert_one(dict(user_doc))
    return user_doc


# ── Invitations ──────────────────────────────────────────────────────────
# Clerk owns the invite lifecycle: it sends the email, tracks pending /
# accepted / revoked, and enforces expiry. The claimant metadata this app
# needs travels in `public_metadata`, which Clerk copies from the invitation
# onto the user it creates — that is what get_or_create_user reads back to
# attach the claimant label and the inviting case worker.
#
# NOTE: the invitation email is now Clerk's template, not the hand-built
# Illinois-blue HTML this app used to send. Restyle it in the Clerk dashboard
# under Customization -> Emails if you want the brand back.


def create_invitation(
    email: str,
    redirect_url: str,
    claimant_label: str = "Primary",
    invited_by: str = "",
    note: str = "",
    expires_in_days: int = 14,
) -> dict:
    """Create and send a Clerk invitation."""
    return _clerk_request(
        "POST",
        "/invitations",
        json={
            "email_address": email,
            "redirect_url": redirect_url,
            "public_metadata": {
                "claimant_label": claimant_label or "Primary",
                "invited_by": invited_by,
                "note": note,
            },
            "notify": True,
            # Clerk rejects a second pending invitation for the same address
            # unless this is set; without it, re-inviting someone whose first
            # invite is still outstanding just errors.
            "ignore_existing": True,
            "expires_in_days": expires_in_days,
        },
    )


def list_invitations(limit: int = 100) -> list:
    """List invitations, newest first."""
    result = _clerk_request(
        "GET", f"/invitations?limit={limit}&order_by=-created_at"
    )
    # Clerk has returned either a bare list or {data: [...]} across API
    # versions — accept both rather than depending on which one is live.
    if isinstance(result, dict):
        return result.get("data", [])
    return result or []


def revoke_invitation(invitation_id: str) -> dict:
    """Revoke a pending invitation."""
    return _clerk_request("POST", f"/invitations/{invitation_id}/revoke")
