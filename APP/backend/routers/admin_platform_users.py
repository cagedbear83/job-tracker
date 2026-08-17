# Ported from admin_portal/admin_users.py and adapted to this codebase's
# router conventions (routers/*.py + core.py, see routers/admin.py for the
# pattern this mirrors).
#
# Admin platform: Users module (read views).
#
# Staff and platform_admin can search/list users and view account METADATA.
# Viewing claimant PII (work-search contacts) is a separate, audited action —
# support_staff get it only ticket-scoped; platform_admin always. Metadata
# never includes password hashes or raw PII.
#
# Mounted at /api/admin/platform/users — see "why /platform" in
# routers/admin_platform_compliance.py's module docstring / the integration
# report. This is DELIBERATELY namespaced apart from the legacy
# /api/admin/users endpoint (routers/admin.py, GET admin_list_users), which
# has a different response shape (a flat list, decorated with
# claimants_count/weeks_count/contacts_count) and is relied upon by the
# existing test suite (tests/test_round2.py::test_admin_list_users) and by
# whatever frontend already consumes it. We did not touch that endpoint.
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from core import db
from rbac import require_staff, require_admin, PlatformRole, _role_of
from admin_audit import log_admin_action, AuditAction
from subscription import get_user_tier  # existing tier resolver

router = APIRouter(prefix="/admin/platform/users", tags=["admin-platform:users"])

# Fields safe to project for any staff-level viewer. NEVER include password_hash.
_METADATA_PROJECTION = {
    "_id": 0,
    "id": 1,
    "email": 1,
    "created_at": 1,
    "email_verified": 1,
    "role": 1,
    "platform_role": 1,
    "org_role": 1,
    "org_id": 1,
}


async def _decorate_with_tier(db, user: dict) -> dict:
    user = dict(user)
    user["subscription_tier"] = (await get_user_tier(db, user["id"])).value
    user["claimant_count"] = await db.profiles.count_documents({"user_id": user["id"]})
    return user


@router.get("", dependencies=[Depends(require_staff)])
async def list_users(
    q: Optional[str] = Query(None, description="email substring search"),
    limit: int = Query(25, le=100),
    skip: int = Query(0, ge=0),
):
    query: dict = {}
    if q:
        query["email"] = {"$regex": q.strip(), "$options": "i"}
    cur = db.users.find(query, _METADATA_PROJECTION).sort("created_at", -1).skip(skip).limit(limit)
    users = [await _decorate_with_tier(db, u) async for u in cur]
    total = await db.users.count_documents(query)
    return {"users": users, "total": total, "skip": skip, "limit": limit}


@router.get("/{user_id}", dependencies=[Depends(require_staff)])
async def get_user(user_id: str):
    user = await db.users.find_one({"id": user_id}, _METADATA_PROJECTION)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    user = await _decorate_with_tier(db, user)
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    user["subscription"] = sub
    return user


@router.get("/{user_id}/pii")
async def view_user_pii(
    user_id: str,
    request: Request,
    ticket_id: Optional[str] = Query(None),
    viewer: dict = Depends(require_staff),
):
    """
    Claimant PII (work-search contacts). Audited on every access.
    Support staff MUST supply a ticket_id (scoped access). platform_admin may
    omit it.
    """
    role = _role_of(viewer)
    if role == PlatformRole.SUPPORT_STAFF and not ticket_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Support staff must provide a ticket_id to view claimant PII.",
        )

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    contacts = [c async for c in db.contacts.find({"user_id": user_id}, {"_id": 0}).limit(500)]

    await log_admin_action(
        db,
        actor_id=viewer["id"],
        actor_role=role.value,
        action=AuditAction.PII_VIEW,
        target_user_id=user_id,
        reason=f"ticket:{ticket_id}" if ticket_id else "admin direct view",
        request_ip=request.client.host if request.client else None,
        metadata={"record_count": len(contacts)},
    )
    return {"user": user, "contacts": contacts}
