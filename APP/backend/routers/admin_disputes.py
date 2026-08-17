# Admin platform: Disputes module — the response workflow for Stripe
# chargebacks. Pairs with Disputes.py (the dependency-injected engine: rate
# metrics, evidence assembly, Stripe submission).
#
# This file didn't exist in the staged admin_portal files or in job-tracker's
# backend — admin_router.py referenced it but it was never shipped. Built
# fresh here, following the same pattern as the other admin_platform_*.py
# routers (core.db, rbac gates, admin_audit trail) and matching the request
# shapes the frontend already expects (src/lib/adminApi.js /
# src/pages/AdminPlatform.jsx's DisputesPanel/DisputeDetail, which were
# written against these exact endpoints in the original admin_portal port).
#
# Mounted at /api/admin/platform/disputes — same namespacing rationale as
# every other admin_platform_*.py router (see
# routers/admin_platform_compliance.py's docstring).
from __future__ import annotations

import os
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from core import db
from rbac import require_staff, require_admin, verify_step_up
from admin_audit import log_admin_action, AuditAction
import Disputes as dispute_engine

# Idempotent — billing.py already sets this at import time when it's loaded,
# but admin_disputes.py may import before billing.py has, so set it here too.
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

router = APIRouter(prefix="/admin/platform/disputes", tags=["admin-platform:disputes"])


class SubmitEvidence(BaseModel):
    step_up_password: str
    overrides: dict = Field(default_factory=dict, description="optional evidence field overrides")


class MarkSubmitted(BaseModel):
    note: str = Field("", description="e.g. 'submitted in Stripe dashboard'")


@router.get("", dependencies=[Depends(require_staff)])
async def list_disputes(limit: int = 100):
    """
    Trailing chargeback-rate metrics plus open/recent disputes, soonest
    evidence deadline first. Disputes are populated by billing.py's Stripe
    webhook handler (charge.dispute.created/updated) — until a real dispute
    event arrives this list is legitimately empty, not broken.
    """
    metrics = await dispute_engine.compute_metrics(db)
    cur = db.disputes.find({}, {"_id": 0}).sort(
        [("evidence_due_by", 1), ("created_at", -1)]
    ).limit(limit)
    disputes = [d async for d in cur]
    return {"metrics": metrics, "disputes": disputes}


@router.get("/{dispute_id}")
async def get_dispute(dispute_id: str, request: Request, viewer: dict = Depends(require_staff)):
    """
    Dispute record + assembled Stripe-evidence draft. Evidence assembly pulls
    the associated user's account/usage data (not raw claimant PII), so this
    is audited the same way user PII views are.
    """
    dispute = await db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dispute not found.")

    evidence = await dispute_engine.gather_evidence(
        db, dispute.get("user_id"), dispute_engine._refund_policy_url()
    )

    await log_admin_action(
        db,
        actor_id=viewer["id"],
        actor_role=viewer.get("platform_role") or viewer.get("role", "staff"),
        action=AuditAction.PII_VIEW,
        target_user_id=dispute.get("user_id"),
        reason="dispute evidence review",
        request_ip=request.client.host if request.client else None,
        metadata={"dispute_id": dispute_id},
    )
    return {"dispute": dispute, "assembled_evidence": evidence}


@router.post("/{dispute_id}/submit")
async def submit_dispute(dispute_id: str, body: SubmitEvidence, request: Request,
                         admin: dict = Depends(require_admin)):
    """Submit assembled evidence to Stripe directly (platform_admin, step-up)."""
    await verify_step_up(admin, body.step_up_password)

    dispute = await db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dispute not found.")

    evidence = await dispute_engine.gather_evidence(
        db, dispute.get("user_id"), dispute_engine._refund_policy_url()
    )
    evidence.update(body.overrides or {})

    try:
        dispute_engine.submit_evidence(stripe, dispute_id, evidence, submit=True)
    except stripe.error.StripeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe rejected the submission: {e}")

    await db.disputes.update_one(
        {"id": dispute_id},
        {"$set": {"status": "under_review", "submitted_by": admin["id"]}},
    )
    await log_admin_action(
        db, actor_id=admin["id"], actor_role="platform_admin",
        action=AuditAction.DISPUTE_SUBMIT, target_user_id=dispute.get("user_id"),
        before=dispute, after={"status": "under_review"},
        request_ip=request.client.host if request.client else None,
        metadata={"dispute_id": dispute_id},
    )
    return {"ok": True}


@router.post("/{dispute_id}/mark-submitted")
async def mark_submitted(dispute_id: str, body: MarkSubmitted, request: Request,
                         viewer: dict = Depends(require_staff)):
    """Record that evidence was submitted manually in the Stripe dashboard (no API call)."""
    dispute = await db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not dispute:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dispute not found.")

    await db.disputes.update_one(
        {"id": dispute_id},
        {"$set": {"status": "under_review", "submitted_by": viewer["id"], "submission_note": body.note}},
    )
    await log_admin_action(
        db, actor_id=viewer["id"],
        actor_role=viewer.get("platform_role") or viewer.get("role", "staff"),
        action=AuditAction.DISPUTE_SUBMIT, target_user_id=dispute.get("user_id"),
        before=dispute, after={"status": "under_review"}, reason=body.note,
        request_ip=request.client.host if request.client else None,
        metadata={"dispute_id": dispute_id, "via": "dashboard"},
    )
    return {"ok": True}
