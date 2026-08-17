"""
Bootstrap the FIRST platform_admin (admin-platform surface). Run ONCE, manually.

Ported from admin_portal/bootstrap_admin.py. Adapted: `db` lives in core.py
in this codebase (server.py just re-exports it), not in `server` directly
as a first-class module-level definition — updated the import accordingly.

No signup path can ever produce a platform_admin. This script promotes
exactly one existing, already-registered user to platform_admin, identified
by the BOOTSTRAP_ADMIN_EMAIL env var. After this, only an existing
platform_admin can promote others (via the portal's future role-grant flow
— not built yet, see the integration report).

NOTE: this is independent of, and does not replace, the legacy
`role: "admin"` account seeded by core.py's ADMIN_EMAIL/ADMIN_PASSWORD
startup hook. rbac.py's `_role_of` already treats `role == "admin"` users
as platform_admin automatically (backward-compat fallback), so for a
single-admin setup you likely do NOT need to run this script at all. Use it
only if you want a distinct account with platform_role=platform_admin that
does NOT also have the legacy role="admin" (e.g. a support_staff promotion
path, or separating "legacy admin" from "new admin-platform admin").

Run:
    BOOTSTRAP_ADMIN_EMAIL=someone@example.com python bootstrap_admin.py

Idempotent: re-running when the user is already admin is a no-op.
Refuses to run if BOOTSTRAP_ADMIN_EMAIL is unset (prevents accidental promotion).
"""

from __future__ import annotations

import asyncio
import os
import sys

from core import db  # <-- SEAM (adapted): db is defined in core.py
from admin_audit import log_admin_action, AuditAction
from rbac import PlatformRole


async def main() -> int:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    if not email:
        print("ERROR: BOOTSTRAP_ADMIN_EMAIL is not set. Aborting.", file=sys.stderr)
        return 2

    user = await db.users.find_one({"email": email})
    if not user:
        print(f"ERROR: no registered user with email {email!r}. "
              f"Register the account first, then re-run.", file=sys.stderr)
        return 3

    current = user.get("platform_role", PlatformRole.USER.value)
    if current == PlatformRole.PLATFORM_ADMIN.value:
        print(f"OK: {email} is already platform_admin. No change.")
        return 0

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"platform_role": PlatformRole.PLATFORM_ADMIN.value}},
    )
    await log_admin_action(
        db,
        actor_id="__bootstrap__",
        actor_role="system",
        action=AuditAction.ROLE_GRANT,
        target_user_id=user["id"],
        before={"platform_role": current},
        after={"platform_role": PlatformRole.PLATFORM_ADMIN.value},
        reason="Initial platform admin bootstrap via BOOTSTRAP_ADMIN_EMAIL.",
    )
    print(f"OK: promoted {email} to platform_admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
