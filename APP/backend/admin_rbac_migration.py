"""
Migration: introduce platform_role on the users collection (admin-platform
surface). Ported from admin_portal/admin_rbac_migration.py.

Adapted: `db` is imported from core.py (server.py just re-exports it).

Safe to run multiple times. Backfills every existing user to the default
'user' platform_role (no one becomes a platform_admin here — that's
bootstrap_admin.py's job; and note rbac.py already treats legacy
role=="admin" users as platform_admin even without running this migration —
see bootstrap_admin.py's docstring), and creates a partial index so
admin/staff lookups stay fast without bloating the index with every
ordinary 'user' row.

Run:
    python admin_rbac_migration.py
"""

from __future__ import annotations

import asyncio

from core import db  # <-- SEAM (adapted): db is defined in core.py
from rbac import PlatformRole


async def main() -> None:

    # 1) Backfill missing platform_role -> "user"
    res = await db.users.update_many(
        {"platform_role": {"$exists": False}},
        {"$set": {"platform_role": PlatformRole.USER.value}},
    )
    print(f"Backfilled platform_role on {res.modified_count} users.")

    # 2) Partial index: only index privileged rows (staff/admin), which are rare.
    await db.users.create_index(
        "platform_role",
        name="platform_role_privileged",
        partialFilterExpression={
            "platform_role": {"$in": [
                PlatformRole.SUPPORT_STAFF.value,
                PlatformRole.PLATFORM_ADMIN.value,
            ]}
        },
    )
    print("Created partial index platform_role_privileged.")

    # 3) Audit log indexes for the compliance module's queries.
    await db.admin_audit_log.create_index([("target_user_id", 1), ("at", -1)])
    await db.admin_audit_log.create_index([("actor_id", 1), ("at", -1)])
    await db.admin_audit_log.create_index([("action", 1), ("at", -1)])
    print("Created admin_audit_log indexes.")


if __name__ == "__main__":
    asyncio.run(main())
