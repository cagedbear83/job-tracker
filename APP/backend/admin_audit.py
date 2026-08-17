"""
Admin audit log — every sensitive platform action writes an immutable record.

This is the PIPA/BIPA paper trail for the admin-platform surface. Comps,
refund approvals, role grants, and any claimant-PII access by staff MUST
call log_admin_action.

Collection: db.admin_audit_log  (append-only by convention; never update/delete)

Ported unchanged from admin_portal/admin_audit.py — this module never
imported from `server`/`core` in the first place (db is passed in as a
parameter to every function), so no adaptation was required here. It is a
separate collection from the existing per-user `db.audit_log` written by
core.log_audit() / exposed at GET /api/audit-log (routers/audit.py) — that
collection tracks a claimant's own actions (CREATE/UPDATE/DELETE on their
weeks & contacts); this one tracks STAFF actions taken on OTHER users'
accounts. Keeping them separate is intentional, not an oversight.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AuditAction(str, Enum):
    COMP_GRANT = "comp_grant"
    COMP_REVOKE = "comp_revoke"
    REFUND_APPROVE = "refund_approve"
    REFUND_MARK_EXECUTED = "refund_mark_executed"
    ROLE_GRANT = "role_grant"
    ROLE_REVOKE = "role_revoke"
    PII_VIEW = "pii_view"                # staff opened claimant contacts/docs
    USER_VIEW = "user_view"              # metadata-only view (optional, noisy)
    DISPUTE_SUBMIT = "dispute_submit"    # evidence submitted to Stripe (API or dashboard)


async def log_admin_action(
    db,
    *,
    actor_id: str,
    actor_role: str,
    action: AuditAction,
    target_user_id: Optional[str] = None,
    before: Any = None,
    after: Any = None,
    reason: Optional[str] = None,
    request_ip: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Append one audit record. If the write fails, we DO raise, because an
    unlogged sensitive action is worse than a failed one (fail closed on
    accountability).
    """
    doc = {
        "actor_id": actor_id,
        "actor_role": actor_role,
        "action": action.value if isinstance(action, AuditAction) else action,
        "target_user_id": target_user_id,
        "before": before,
        "after": after,
        "reason": reason,
        "request_ip": request_ip,
        "metadata": metadata or {},
        "at": datetime.now(timezone.utc),
    }
    await db.admin_audit_log.insert_one(doc)


async def query_audit(
    db,
    *,
    target_user_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    q: dict = {}
    if target_user_id:
        q["target_user_id"] = target_user_id
    if actor_id:
        q["actor_id"] = actor_id
    if action:
        q["action"] = action
    cur = db.admin_audit_log.find(q, {"_id": 0}).sort("at", -1).limit(limit)
    return [d async for d in cur]
