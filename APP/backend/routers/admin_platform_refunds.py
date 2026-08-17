# Ported from admin_portal/admin_refunds.py.
#
# Admin platform: Refunds module.
#
# The portal owns the DECISION RECORD, Stripe owns the MONEY. There is
# deliberately NO refund-scoped Stripe key wired into the app. Flow:
#
#     staff/anyone -> create request        (status: requested)
#     platform_admin -> approve  (step-up)  (status: approved)  <- decision made
#     platform_admin -> mark executed       (status: executed)  <- after doing
#                                                                    it in Stripe
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from core import db
from rbac import require_staff, require_admin, verify_step_up
from admin_audit import log_admin_action, AuditAction

router = APIRouter(prefix="/admin/platform/refunds", tags=["admin-platform:refunds"])


class RefundStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    EXECUTED = "executed"
    DENIED = "denied"


class RefundCreate(BaseModel):
    user_id: str
    amount_cents: int = Field(..., gt=0)
    currency: str = "usd"
    reason: str = Field(..., min_length=3)
    stripe_charge_id: Optional[str] = None


class RefundDecision(BaseModel):
    note: str = Field(..., min_length=3)
    step_up_password: str


@router.get("", dependencies=[Depends(require_staff)])
async def list_refunds(status_filter: Optional[str] = None, limit: int = 50):
    q = {"status": status_filter} if status_filter else {}
    cur = db.refund_requests.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return {"refunds": [r async for r in cur]}


@router.post("", dependencies=[Depends(require_staff)])
async def create_refund(body: RefundCreate, viewer: dict = Depends(require_staff)):
    rec = {
        "id": str(uuid4()),
        "user_id": body.user_id,
        "amount_cents": body.amount_cents,
        "currency": body.currency,
        "reason": body.reason,
        "stripe_charge_id": body.stripe_charge_id,
        "status": RefundStatus.REQUESTED.value,
        "requested_by": viewer["id"],
        "created_at": datetime.now(timezone.utc),
    }
    await db.refund_requests.insert_one(rec)
    rec.pop("_id", None)
    return rec


@router.post("/{refund_id}/approve")
async def approve_refund(refund_id: str, body: RefundDecision, request: Request,
                         admin: dict = Depends(require_admin)):
    await verify_step_up(admin, body.step_up_password)
    rec = await db.refund_requests.find_one({"id": refund_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Refund request not found.")
    if rec["status"] != RefundStatus.REQUESTED.value:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Cannot approve from status '{rec['status']}'.")

    await db.refund_requests.update_one(
        {"id": refund_id},
        {"$set": {"status": RefundStatus.APPROVED.value,
                  "approved_by": admin["id"], "approval_note": body.note,
                  "approved_at": datetime.now(timezone.utc)}},
    )
    await log_admin_action(
        db, actor_id=admin["id"], actor_role="platform_admin",
        action=AuditAction.REFUND_APPROVE, target_user_id=rec["user_id"],
        before=rec, after={"status": "approved"}, reason=body.note,
        request_ip=request.client.host if request.client else None,
        metadata={"refund_id": refund_id, "amount_cents": rec["amount_cents"]},
    )
    # NOTE: money is NOT moved here. Execute the refund in the Stripe dashboard,
    # then call /mark-executed to close the loop.
    return {"ok": True, "next": "Execute in Stripe dashboard, then mark executed."}


@router.post("/{refund_id}/mark-executed")
async def mark_executed(refund_id: str, request: Request,
                        admin: dict = Depends(require_admin)):
    rec = await db.refund_requests.find_one({"id": refund_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Refund request not found.")
    if rec["status"] != RefundStatus.APPROVED.value:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Only approved refunds can be marked executed.")
    await db.refund_requests.update_one(
        {"id": refund_id},
        {"$set": {"status": RefundStatus.EXECUTED.value,
                  "executed_by": admin["id"],
                  "executed_at": datetime.now(timezone.utc)}},
    )
    await log_admin_action(
        db, actor_id=admin["id"], actor_role="platform_admin",
        action=AuditAction.REFUND_MARK_EXECUTED, target_user_id=rec["user_id"],
        before=rec, after={"status": "executed"},
        request_ip=request.client.host if request.client else None,
        metadata={"refund_id": refund_id},
    )
    return {"ok": True}
