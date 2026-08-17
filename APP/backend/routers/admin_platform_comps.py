# Ported from admin_portal/admin_comps.py.
#
# Admin platform: Comps module (platform-admin only).
#
# A "comp" = the platform owner granting free paid-tier access at the
# platform's own cost (beta testers, press, goodwill).
#
# A comp is represented as a subscription record with comp=True, so all
# existing gating logic (subscription.get_user_tier -> get_tier_limits)
# works unchanged. Expiry is enforced by comp_expires_at being written into
# current_period_end (see subscription.get_user_tier's period_end handling).
#
# ADAPTATION NOTE: the original _COMPABLE_TIERS was `{"pro", "case_worker"}`.
# This codebase's actual subscription.Tier enum (subscription.py) spells the
# top tier `"caseworker"` (no underscore) — `Tier.CASEWORKER = "caseworker"`.
# Using the original "case_worker" string would have silently written
# subscription records with a tier value subscription.get_user_tier() could
# never resolve to a real Tier (Tier("case_worker") raises ValueError),
# 500-ing every gated route for that comped user. Fixed to match the real
# enum value here.
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from core import db
from rbac import require_admin, verify_step_up
from admin_audit import log_admin_action, AuditAction

router = APIRouter(prefix="/admin/platform/comps", tags=["admin-platform:comps"])

_COMPABLE_TIERS = {"pro", "caseworker"}  # must match subscription.Tier values


class CompGrantRequest(BaseModel):
    user_id: str
    tier: str = Field(..., description="pro | caseworker")
    expires_at: Optional[datetime] = Field(
        None, description="UTC expiry; null = open-ended (discouraged)"
    )
    reason: str = Field(..., min_length=3)
    step_up_password: str


class CompRevokeRequest(BaseModel):
    user_id: str
    reason: str = Field(..., min_length=3)
    step_up_password: str


def _is_test_mode() -> bool:
    return os.environ.get("STRIPE_SECRET_KEY", "").startswith("sk_test_") or \
        os.environ.get("APP_ENV", "").lower() in {"dev", "test", "development"}


async def _active_comp_count(db) -> int:
    return await db.subscriptions.count_documents({
        "comp": True,
        "status": "active",
    })


@router.get("/status", dependencies=[Depends(require_admin)])
async def comp_status():
    cap_raw = os.environ.get("PLATFORM_COMP_CAP")
    cap = int(cap_raw) if cap_raw and cap_raw.isdigit() else None
    active = await _active_comp_count(db)
    return {
        "active_comps": active,
        "cap": cap,
        "cap_enforced": cap is not None,
        "test_mode": _is_test_mode(),
        "note": None if cap is not None else
        "No PLATFORM_COMP_CAP set — comps are uncapped (intentionally open).",
    }


@router.post("/grant")
async def grant_comp(body: CompGrantRequest, request: Request,
                     admin: dict = Depends(require_admin)):
    await verify_step_up(admin, body.step_up_password)

    if body.tier not in _COMPABLE_TIERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"tier must be one of {sorted(_COMPABLE_TIERS)}")

    target = await db.users.find_one({"id": body.user_id}, {"_id": 0, "id": 1})
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target user not found.")

    # Cap enforcement — production only, only when a cap is configured.
    cap_raw = os.environ.get("PLATFORM_COMP_CAP")
    cap = int(cap_raw) if cap_raw and cap_raw.isdigit() else None
    if cap is not None and not _is_test_mode():
        if await _active_comp_count(db) >= cap:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Comp cap reached ({cap} active). Revoke one before granting.",
            )

    before = await db.subscriptions.find_one({"user_id": body.user_id}, {"_id": 0})
    now = datetime.now(timezone.utc)

    # ADAPTATION / BUG FIX: the original admin_portal code wrote
    # `current_period_end: body.expires_at` verbatim, treating None as
    # "open-ended" — that assumed a get_user_tier() that special-cased a
    # missing period_end as unlimited access. This codebase's actual
    # subscription.get_user_tier() (subscription.py) does NOT do that: when
    # current_period_end is None it instead falls back to a short grace
    # window (SUBSCRIPTION_GRACE_DAYS, default 3 days) measured from the
    # record's `updated_at`/`created_at` — fields this comp record never
    # set. Net effect, confirmed by manual testing against this
    # integration: an "open-ended" comp with no expiry was resolved as tier
    # FREE immediately, not the intended paid tier. Fixed by giving a truly
    # open-ended comp (expires_at not supplied) a far-future period_end
    # instead of None, so it takes the normal "period_end in the future"
    # path in get_user_tier() rather than the grace-window fallback.
    effective_period_end = body.expires_at or (now + timedelta(days=365 * 100))

    new_sub = {
        "user_id": body.user_id,
        "tier": body.tier,
        "status": "active",
        "comp": True,
        "comped_by": admin["id"],
        "comp_reason": body.reason,
        "comp_granted_at": now,
        "updated_at": now,
        "current_period_end": effective_period_end,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
    }
    await db.subscriptions.update_one(
        {"user_id": body.user_id}, {"$set": new_sub}, upsert=True
    )
    await log_admin_action(
        db, actor_id=admin["id"], actor_role="platform_admin",
        action=AuditAction.COMP_GRANT, target_user_id=body.user_id,
        before=before, after=new_sub, reason=body.reason,
        request_ip=request.client.host if request.client else None,
    )
    return {"ok": True, "comp": new_sub}


@router.post("/revoke")
async def revoke_comp(body: CompRevokeRequest, request: Request,
                      admin: dict = Depends(require_admin)):
    await verify_step_up(admin, body.step_up_password)

    sub = await db.subscriptions.find_one({"user_id": body.user_id}, {"_id": 0})
    if not sub or not sub.get("comp"):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No active comp for that user.")

    # Revoking a comp drops them to free (data stays; account-deletion purge
    # is the separate, opt-in job in core.py).
    await db.subscriptions.update_one(
        {"user_id": body.user_id},
        {"$set": {"status": "canceled", "comp": False,
                  "comp_revoked_at": datetime.now(timezone.utc),
                  "comp_revoked_by": admin["id"]}},
    )
    await log_admin_action(
        db, actor_id=admin["id"], actor_role="platform_admin",
        action=AuditAction.COMP_REVOKE, target_user_id=body.user_id,
        before=sub, after=None, reason=body.reason,
        request_ip=request.client.host if request.client else None,
    )
    return {"ok": True}
