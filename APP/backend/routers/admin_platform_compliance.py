# Ported from admin_portal/admin_compliance.py.
#
# Admin platform: Compliance module.
#
# Two read surfaces:
#   1) Audit-log search over admin_audit_log (staff actions on other users).
#   2) Retention monitor — benefit weeks approaching the 53-week mark that
#      Illinois UI record-retention guidance commonly cites. See
#      retention.py's module docstring for an important caveat: this
#      codebase has no actual scheduled job that deletes benefit_weeks on
#      that schedule (only the unrelated 30-day account-purge job in
#      core.py). This panel is a read-only projection, not a live job
#      status. `appeal_hold` is likewise a field this schema doesn't
#      currently populate anywhere — the query for it is harmless (matches
#      nothing) and forward-compatible if that field is added later.
#
# READ-ONLY.
#
# WHY THIS WHOLE ADMIN-PLATFORM SURFACE LIVES UNDER /api/admin/platform/*
# rather than /api/admin/* :
# admin_portal/admin_router.py originally mounted every sub-router straight
# under /api/admin, e.g. GET /api/admin/users. This codebase's existing
# routers/admin.py ALREADY defines GET /api/admin/users (a flat list
# decorated with claimants_count/weeks_count/contacts_count, gated by the
# legacy `role == "admin"` check) and it's asserted on by
# tests/test_round2.py::test_admin_list_users. The ported admin_users
# module returns a materially different shape ({users, total, skip, limit})
# under the SAME path/method, which would silently shadow (or be shadowed
# by, depending on router registration order) the existing, tested
# endpoint. Rather than overwrite tested behavior or hand-merge two
# different response shapes into one endpoint, every new admin_platform_*
# router is mounted one level deeper, under /api/admin/platform/*. This:
#   - preserves 100% of the existing /api/admin/* behavior untouched
#   - adds the new capabilities (comps, refunds, PII-audit view, system
#     health, compliance/retention) at clearly-namespaced paths
#   - keeps both admin surfaces addressable side by side if/when someone
#     wants to consolidate them later
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from core import db
from rbac import require_staff
from admin_audit import query_audit
from retention import deletion_date_for, today_chicago

router = APIRouter(prefix="/admin/platform/compliance", tags=["admin-platform:compliance"])


@router.get("/audit", dependencies=[Depends(require_staff)])
async def audit_search(
    target_user_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(100, le=500),
):
    rows = await query_audit(
        db, target_user_id=target_user_id, actor_id=actor_id,
        action=action, limit=limit,
    )
    return {"entries": rows, "count": len(rows)}


@router.get("/retention", dependencies=[Depends(require_staff)])
async def retention_monitor(within_days: int = Query(14, le=60)):
    """
    Benefit weeks whose 53-week projected deletion date falls within
    `within_days`, plus the set of accounts under an active appeal hold.
    week_end is parsed from its stored 'YYYY-MM-DD' string; weeks on held
    accounts are flagged (they would be exempt from any future deletion job).
    """
    today = today_chicago()

    # Accounts under an active appeal hold (field not populated anywhere in
    # this codebase yet — see module docstring; query is harmless).
    held = set()
    held_accounts = []
    async for u in db.users.find({"appeal_hold.active": True},
                                 {"_id": 0, "id": 1, "email": 1, "appeal_hold": 1}):
        held.add(u["id"])
        held_accounts.append({
            "user_id": u["id"], "email": u.get("email"),
            "appeal_date": (u.get("appeal_hold") or {}).get("appeal_date"),
        })

    items = []
    async for w in db.benefit_weeks.find({}, {"_id": 0}):
        dd = deletion_date_for(w.get("week_end"))
        if not dd:
            continue
        days_left = (dd - today).days
        if days_left > within_days:
            continue
        items.append({
            "user_id": w.get("user_id"),
            "week_start": w.get("week_start"),
            "week_end": w.get("week_end"),
            "deletion_date": dd.isoformat(),
            "days_until_deletion": days_left,
            "notices_sent": w.get("retention_notices_sent", []),
            "on_hold": w.get("user_id") in held,
        })
    items.sort(key=lambda x: x["days_until_deletion"])
    return {
        "as_of": today.isoformat(),
        "within_days": within_days,
        "count": len(items),
        "weeks": items,
        "held_accounts": held_accounts,
    }
