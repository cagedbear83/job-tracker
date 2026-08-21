"""
Platform RBAC — authorization layer for the Admin portal (ported from the
standalone admin_portal module).

This sits ON TOP of the existing authentication (get_current_user, password
policy, login_attempts lockout in core.py). It does NOT replace any of that,
and it does NOT replace the legacy binary `role` field ("user" / "admin")
that the pre-existing routers/admin.py, routers/invites.py, etc. already
gate on via `core.require_admin`. Those keep working unchanged.

THREE ORTHOGONAL DIMENSIONS on a user — do not conflate:
    platform_role    -> authority in the NEW admin-platform surface  [this file]
    org_role         -> authority inside a Case Worker org           [later build]
    subscription_tier-> billing / feature gating                     [subscription.py]

INTEGRATION NOTES (adapted from the original admin_portal/rbac.py):
  - Original imported `get_current_user, verify_password, db` from `server`.
    In this codebase server.py is just the composition root (it does
    `from core import *`); the actual definitions live in core.py. Updated
    the import accordingly.
  - Original `_role_of` looked ONLY at `user["platform_role"]`, defaulting an
    unset/unknown value to PlatformRole.USER. That would silently lock out
    the site's existing `role == "admin"` account(s) (e.g. the account
    seeded from ADMIN_EMAIL/ADMIN_PASSWORD in core.py's startup hook) from
    every new admin-platform endpoint until someone manually ran
    admin_rbac_migration.py + bootstrap_admin.py. Since this codebase
    already has a working, tested admin concept (`role == "admin"`), we
    added a backward-compat fallback: if `platform_role` isn't set on the
    user doc, an existing legacy admin (`role == "admin"`) is treated as
    PLATFORM_ADMIN. This is a deliberate, non-obvious adaptation — flagged
    here and in the integration report.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status

# ─── SEAM (adapted) ──────────────────────────────────────────────────────
# db and get_current_user both live in core.py in this codebase (server.py
# just re-exports them via `from core import *`). verify_password is gone —
# Clerk owns credentials now; see verify_step_up below.
from core import get_current_user, db  # <-- SEAM (adapted)
# ────────────────────────────────────────────────────────────────────────


class PlatformRole(str, Enum):
    USER = "user"                    # default — every account starts here
    SUPPORT_STAFF = "support_staff"  # read-mostly triage
    PLATFORM_ADMIN = "platform_admin"  # full authority


# Ordered privilege ladder. A role satisfies a requirement if its rank is >=.
_RANK = {
    PlatformRole.USER: 0,
    PlatformRole.SUPPORT_STAFF: 1,
    PlatformRole.PLATFORM_ADMIN: 2,
}


def _role_of(user: dict) -> PlatformRole:
    """
    Resolve a user's platform role.

    1. If `platform_role` is explicitly set (post-migration / manually
       granted support_staff), honor it.
    2. Otherwise fall back to the legacy `role` field so existing admins
       (role == "admin") are not locked out of the new admin-platform
       surface. This mirrors core.require_admin's own check so the two
       admin systems agree for the common case of a single admin account.
    3. Anything else defaults to USER (fail closed to least privilege).
    """
    raw = (user or {}).get("platform_role")
    if raw:
        try:
            return PlatformRole(raw)
        except ValueError:
            pass  # unknown value in the DB -> fall through to legacy check

    if (user or {}).get("role") == "admin":
        return PlatformRole.PLATFORM_ADMIN

    return PlatformRole.USER


def has_at_least(user: dict, required: PlatformRole) -> bool:
    return _RANK[_role_of(user)] >= _RANK[required]


def require_platform_role(required: PlatformRole) -> Callable:
    """
    FastAPI dependency factory. Usage:

        @router.get("/x", dependencies=[Depends(require_platform_role(
            PlatformRole.SUPPORT_STAFF))])

    or, to also receive the user object:

        async def handler(admin: dict = Depends(require_platform_role(
            PlatformRole.PLATFORM_ADMIN))):
    """
    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if not has_at_least(user, required):
            # 404-style opacity would be nicer, but 403 is fine for an
            # authenticated portal. Do NOT leak which role was required.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges.",
            )
        return user
    return _dep


# Convenience shorthands — the two roles the portal actually gates on.
require_staff = require_platform_role(PlatformRole.SUPPORT_STAFF)
require_admin = require_platform_role(PlatformRole.PLATFORM_ADMIN)
# NOTE: this shadows the *name* core.require_admin only within modules that
# `from rbac import require_admin` explicitly (i.e. the new admin_platform_*
# routers). routers/admin.py, routers/invites.py etc. keep using
# core.require_admin (the legacy role=="admin" check) untouched — the two
# never collide because nothing does `from rbac import *`.


# ─── Step-up re-authentication ──────────────────────────────────────────
# Sensitive actions (comp, refund approve, role grant) re-verify the
# acting admin's password even inside an active session. Call this INSIDE
# the handler, after the role gate, before doing the sensitive thing.

# How recently the acting admin must have proven a factor for a sensitive
# action to be allowed. Clerk reports this per-request, so it is a real
# freshness guarantee rather than a "type your password again" prompt.
STEP_UP_MAX_AGE_MINUTES = 10


class StepUpError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirm your identity to continue.",
            # The frontend keys off this to open Clerk's reverification flow
            # rather than showing a generic permission error.
            headers={"X-Clerk-Reverification": "required"},
        )


async def verify_step_up(user: dict) -> None:
    """Require the acting admin to have re-verified a factor recently.

    Replaces the old scheme, which re-posted the admin's password to our own
    endpoint and compared it against the stored bcrypt hash. Under Clerk
    there is no local hash, and the password never touches this server at
    all — so freshness is read off the session instead.

    Clerk puts `fva` (factor verification age) on the session token as
    [firstFactorAgeMinutes, secondFactorAgeMinutes], where -1 means the
    factor was never used. We require a first factor verified within
    STEP_UP_MAX_AGE_MINUTES.

    Fails closed: a session token without `fva` (an older Clerk token
    version) is rejected rather than waved through.
    """
    claims = user.get("_session_claims") or {}
    fva = claims.get("fva")

    if not isinstance(fva, (list, tuple)) or not fva:
        raise StepUpError()

    try:
        first_factor_age = int(fva[0])
    except (TypeError, ValueError):
        raise StepUpError()

    if first_factor_age < 0 or first_factor_age > STEP_UP_MAX_AGE_MINUTES:
        raise StepUpError()
