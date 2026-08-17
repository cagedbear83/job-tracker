"""
Dispute / chargeback engine (core logic, dependency-injected — no FastAPI
router here; see routers/admin_disputes.py for the HTTP surface).

Used by:
  - billing.py's handle_stripe_webhook()  — ingests charge.succeeded /
    charge.dispute.* Stripe events into the collections below.
  - routers/admin_disputes.py             — the admin portal's response
    workflow (list, evidence assembly, submit-to-Stripe).

Collections:
  disputes         one doc per Stripe dispute (status, amount, reason, due_by, user)
  payment_events   lightweight {created_at} per successful charge (rate denominator)
  dispute_alerts   record of threshold alerts already sent (dedup)

FIX HISTORY (this integration): this file previously failed to import at
all — `tags+["admin:disputes"]` (should be `=`), `overrides: duct = Field(...)`
(typo'd type annotation), a dangling `from server import db` (this codebase's
db lives in core.py, and every function below already takes `db` as an
explicit parameter — the module-level import was unused dead code), and a
stray `import disputes` (self-import — this *is* the disputes module). The
router construction and request models (`SubmitEvidence`, `MarkSubmitted`)
that used to live in this file have moved to routers/admin_disputes.py,
matching this file's own docstring ("no server imports") and the pattern
every other admin_platform_*.py router follows (engine/logic separate from
the router). Nothing here was behaviorally changed beyond fixing the syntax
errors and removing the misplaced router code.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional


def _refund_policy_url() -> str:
    return os.environ.get(
        "REFUND_POLICY_URL",
        f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/refund-policy",
    )


# ── Thresholds (env-overridable; defaults are conservative levels) ──
WARN_RATE = float(os.environ.get("CHARGEBACK_WARN_RATE", "0.005"))       # 0.50%
CRITICAL_RATE = float(os.environ.get("CHARGEBACK_CRITICAL_RATE", "0.0075"))  # 0.75%
CRITICAL_COUNT = int(os.environ.get("CHARGEBACK_CRITICAL_COUNT", "100"))
WINDOW_DAYS = int(os.environ.get("CHARGEBACK_WINDOW_DAYS", "30"))

PRODUCT_DESCRIPTION = (
    "Illinois UI Job Search Tracker — a subscription web application that helps "
    "unemployment claimants log weekly work-search contacts and generate work-search "
    "records. Access is provided immediately upon subscription."
)

_LEVEL_RANK = {"none": 0, "warn": 1, "critical": 2}


def alert_level(rate: float, dispute_count: int) -> str:
    if rate >= CRITICAL_RATE or dispute_count >= CRITICAL_COUNT:
        return "critical"
    if rate >= WARN_RATE:
        return "warn"
    return "none"


async def record_charge(db, stripe_charge_id: str) -> None:
    """Idempotently record a successful charge for the rate denominator."""
    await db.payment_events.update_one(
        {"charge_id": stripe_charge_id},
        {"$setOnInsert": {"charge_id": stripe_charge_id,
                          "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def upsert_dispute(db, d: dict, user_id: Optional[str]) -> dict:
    """Create/update a dispute record from normalized Stripe dispute fields."""
    doc = {
        "id": d["id"],
        "charge_id": d.get("charge_id"),
        "user_id": user_id,
        "amount_cents": d.get("amount_cents"),
        "currency": d.get("currency", "usd"),
        "reason": d.get("reason"),
        "status": d.get("status"),                 # needs_response / under_review / won / lost
        "evidence_due_by": d.get("evidence_due_by"),
        "updated_at": datetime.now(timezone.utc),
    }
    existing = await db.disputes.find_one({"id": d["id"]}, {"_id": 0, "created_at": 1})
    if not existing:
        doc["created_at"] = datetime.now(timezone.utc)
    await db.disputes.update_one({"id": d["id"]}, {"$set": doc}, upsert=True)
    return doc


async def compute_metrics(db, window_days: int = WINDOW_DAYS) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    charges = await db.payment_events.count_documents({"created_at": {"$gte": since}})
    disputes = await db.disputes.count_documents({"created_at": {"$gte": since}})
    rate = (disputes / charges) if charges else 0.0
    return {
        "window_days": window_days,
        "charges": charges,
        "disputes": disputes,
        "rate": rate,
        "rate_pct": round(rate * 100, 3),
        "level": alert_level(rate, disputes),
        "thresholds": {"warn": WARN_RATE, "critical": CRITICAL_RATE,
                       "critical_count": CRITICAL_COUNT},
    }


async def check_and_alert(db, send_email, log_audit, reminder_html,
                          admin_emails: list) -> dict:
    """
    Recompute metrics; if the alert level rose above what we last alerted in this
    window, email the admin(s). Deduped so a flurry of disputes doesn't spam.

    Not currently called anywhere (email alerting wasn't wired into the
    webhook ingestion in this pass — see billing.py's handle_stripe_webhook
    module comment). Left intact for whoever wires it in: it needs a
    send_email(addr, subject, html) callable, a log_audit(actor, action,
    entity, entity_id, detail) callable, and a reminder_html(title, body)
    template renderer, all of which already exist in core.py.
    """
    m = await compute_metrics(db)
    level = m["level"]
    if level == "none":
        return {"alerted": False, "metrics": m}

    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    last = await db.dispute_alerts.find_one(
        {"sent_at": {"$gte": since}}, sort=[("sent_at", -1)]
    )
    last_rank = _LEVEL_RANK.get(last["level"], 0) if last else 0
    if _LEVEL_RANK[level] <= last_rank:
        return {"alerted": False, "metrics": m}  # already alerted at >= this level

    subject = f"⚠ Chargeback rate {level.upper()}: {m['rate_pct']}% ({m['disputes']}/{m['charges']})"
    body = (
        f"<p>Your trailing-{WINDOW_DAYS}-day dispute rate has reached "
        f"<b>{m['rate_pct']}%</b> ({m['disputes']} disputes / {m['charges']} charges), "
        f"crossing the <b>{level}</b> threshold.</p>"
        f"<p>Warn ≥ {WARN_RATE*100:.2f}% · Critical ≥ {CRITICAL_RATE*100:.2f}% "
        f"or {CRITICAL_COUNT} disputes. Card networks penalize merchants above ~0.9%.</p>"
        "<p>Review open disputes in the admin console and respond before their "
        "evidence deadlines.</p>"
    )
    html = reminder_html("Chargeback rate alert", body)
    sent_any = False
    for addr in admin_emails:
        if addr and await send_email(addr, subject, html):
            sent_any = True
    await db.dispute_alerts.insert_one({
        "level": level, "rate": m["rate"], "disputes": m["disputes"],
        "charges": m["charges"], "sent_at": datetime.now(timezone.utc),
    })
    if log_audit:
        await log_audit("system", "CHARGEBACK_ALERT", "dispute", None,
                        f"{level} — {m['rate_pct']}% ({m['disputes']}/{m['charges']})")
    return {"alerted": sent_any, "level": level, "metrics": m}


# ── Evidence assembly ─────────────────────────────────────────────────────
async def gather_evidence(db, user_id: str, refund_policy_url: str) -> dict:
    """Pull local proof-of-service into a Stripe-evidence-shaped dict."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0}) if user_id else None
    profile = await db.profiles.find_one({"user_id": user_id}, {"_id": 0}) if user_id else None
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0}) if user_id else None

    # Login history = strong "they used the service" proof.
    logins = []
    if user_id:
        async for a in db.audit_log.find(
            {"user_id": user_id, "action": "LOGIN"}, {"_id": 0, "timestamp": 1, "detail": 1}
        ).sort("timestamp", -1).limit(25):
            logins.append(a.get("timestamp"))
    weeks = await db.benefit_weeks.count_documents({"user_id": user_id}) if user_id else 0
    contacts = await db.contacts.count_documents({"user_id": user_id}) if user_id else 0

    name = ""
    if profile:
        name = f"{profile.get('first_name','')} {profile.get('last_name','')}".strip() or profile.get("full_name", "")

    access_log = "; ".join(str(t) for t in logins[:25]) if logins else "No login records found."
    usage_summary = (
        f"Account created {user.get('created_at') if user else 'unknown'}. "
        f"Subscription tier: {sub.get('tier') if sub else 'unknown'}, "
        f"status: {sub.get('status') if sub else 'unknown'}. "
        f"Customer actively used the service: {weeks} benefit week(s) and "
        f"{contacts} work-search contact(s) recorded. "
        f"{len(logins)} recent login(s) on record."
    )

    # Explicit terms/refund-policy acceptance, if captured at signup.
    accepted_at = (user or {}).get("terms_accepted_at")
    terms_ver = (user or {}).get("terms_version")
    accepted_ip = (user or {}).get("terms_accepted_ip")
    if accepted_at:
        acceptance = (
            f"Customer expressly accepted the Terms of Service and refund policy "
            f"(version {terms_ver or 'n/a'}) on {accepted_at}"
            + (f" from IP {accepted_ip}" if accepted_ip else "")
            + f". The policy is publicly available at {refund_policy_url}."
        )
    else:
        acceptance = (
            "The refund and cancellation policy is presented at signup and is "
            f"publicly available at {refund_policy_url}."
        )

    return {
        "product_description": PRODUCT_DESCRIPTION,
        "customer_name": name,
        "customer_email_address": (user or {}).get("email", ""),
        "access_activity_log": access_log[:19000],       # Stripe field limits
        "uncategorized_text": usage_summary[:19000],
        "refund_policy_disclosure": (
            acceptance + " Charges appear as 'ILLINOIS UI TRACKER'."
        )[:19000],
    }


async def submit_evidence(stripe, dispute_id: str, evidence: dict, submit: bool = True):
    """
    Send assembled evidence to Stripe. Only non-empty fields are included.
    `stripe` is the configured stripe module (passed by the caller that holds the key).
    """
    clean = {k: v for k, v in evidence.items() if v}
    return stripe.Dispute.modify(dispute_id, evidence=clean, submit=submit)
