"""
subscription.py — Feature gating, tier config, and usage metering for
Illinois UI Job Search Tracker.

Drop this file into APP/backend/subscription.py and import from server.py.
Requires: pip install stripe --break-system-packages
"""

import os
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from fastapi import HTTPException, Depends
from pydantic import BaseModel

# ═══════════════════════════════════════════════════════════════════════
# TIER DEFINITIONS — the single source of truth for what each plan gets
# ═══════════════════════════════════════════════════════════════════════

class Tier(str, Enum):
    FREE = "free"
    PRO = "pro"
    CASEWORKER = "caseworker"


# Stripe Price IDs — create these in the Stripe Dashboard, then set as env
# vars. Six total: each tier has a monthly + annual price, and Case Worker
# splits into a "first seat" price and an "additional seat" price (the
# additional-seat price uses Stripe's quantity field to scale to N seats).
#
# Billing interval is chosen by the user at checkout via a monthly/annual
# toggle; the frontend sends "monthly" or "annual" and the backend picks
# the matching price ID from these maps.
STRIPE_PRICE_IDS = {
    Tier.PRO: {
        "monthly": os.environ.get("STRIPE_PRICE_PRO_MONTHLY", ""),
        "annual": os.environ.get("STRIPE_PRICE_PRO_ANNUAL", ""),
    },
    Tier.CASEWORKER: {
        # First seat — every Case Worker subscription includes exactly one.
        "first_seat_monthly": os.environ.get("STRIPE_PRICE_CW_FIRST_MONTHLY", ""),
        "first_seat_annual": os.environ.get("STRIPE_PRICE_CW_FIRST_ANNUAL", ""),
        # Additional seats — billed via quantity (quantity = seats - 1).
        "additional_seat_monthly": os.environ.get("STRIPE_PRICE_CW_ADDL_MONTHLY", ""),
        "additional_seat_annual": os.environ.get("STRIPE_PRICE_CW_ADDL_ANNUAL", ""),
    },
}


def get_checkout_line_items(tier: Tier, interval: str, seats: int = 1) -> list[dict]:
    """
    Returns the Stripe line_items list for a checkout session.

    - Pro: a single line item (quantity 1).
    - Case Worker: a first-seat line item (qty 1), plus — if seats > 1 —
      an additional-seat line item with quantity = seats - 1.

    interval must be "monthly" or "annual".
    """
    if interval not in ("monthly", "annual"):
        raise ValueError("interval must be 'monthly' or 'annual'")

    if tier == Tier.PRO:
        pid = STRIPE_PRICE_IDS[Tier.PRO][interval]
        return [{"price": pid, "quantity": 1}]

    if tier == Tier.CASEWORKER:
        first_pid = STRIPE_PRICE_IDS[Tier.CASEWORKER][f"first_seat_{interval}"]
        items = [{"price": first_pid, "quantity": 1}]
        if seats > 1:
            addl_pid = STRIPE_PRICE_IDS[Tier.CASEWORKER][f"additional_seat_{interval}"]
            items.append({"price": addl_pid, "quantity": seats - 1})
        return items

    raise ValueError(f"Tier {tier} is not a paid tier")

# Every gated feature lives here. `limit` is a monthly cap; None = unlimited;
# 0 = fully blocked on that tier. This dict is what both backend and
# frontend logic key off of, so keep feature names consistent everywhere.
TIER_LIMITS = {
    Tier.FREE: {
        "max_claimants": 1,
        "sms_reminders": False,
        "email_reminders_full_schedule": False,   # free = 1 fixed reminder/week only
        "ai_screenshot_import": 0,
        "ai_resume_review": 0,
        "calendar_events": False,
        "pdf_exports_per_month": 3,
        "csv_export_full_history": False,
        "document_storage_mb": 0,
        "audit_log_days": 30,
        "advanced_analytics": False,
        "bulk_invite_management": False,
    },
    Tier.PRO: {
        "max_claimants": 1,
        "sms_reminders": True,
        "email_reminders_full_schedule": True,
        "ai_screenshot_import": 10,
        "ai_resume_review": 3,
        "calendar_events": True,
        "pdf_exports_per_month": None,
        "csv_export_full_history": True,
        "document_storage_mb": 100,
        "audit_log_days": 365,
        "advanced_analytics": True,
        "bulk_invite_management": False,
    },
    Tier.CASEWORKER: {
        "max_claimants": None,
        "sms_reminders": True,
        "email_reminders_full_schedule": True,
        "ai_screenshot_import": None,
        "ai_resume_review": None,
        "calendar_events": True,
        "pdf_exports_per_month": None,
        "csv_export_full_history": True,
        "document_storage_mb": 1024,
        "audit_log_days": 365,
        "advanced_analytics": True,
        "bulk_invite_management": True,
    },
}

# Metered features that need a monthly counter reset. Anything with an
# integer limit in TIER_LIMITS (not True/False) should be listed here so
# the usage-tracking code knows to count it.
METERED_FEATURES = [
    "ai_screenshot_import",
    "ai_resume_review",
    "pdf_exports_per_month",
]


# ═══════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════

class SubscriptionStatus(BaseModel):
    tier: Tier = Tier.FREE
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: str = "active"          # active, past_due, canceled, trialing
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class UsageCounter(BaseModel):
    user_id: str
    feature: str
    period: str          # "2026-07" (YYYY-MM) — resets monthly by key rollover
    count: int = 0


# ═══════════════════════════════════════════════════════════════════════
# CORE GATING LOGIC
# ═══════════════════════════════════════════════════════════════════════

def _current_period() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def get_tier_limits(tier: Tier) -> dict:
    return TIER_LIMITS.get(tier, TIER_LIMITS[Tier.FREE])


# When a subscription record has no resolvable current_period_end (e.g. Stripe
# didn't include it in the payload), grant this many days of grace from the
# record's last update instead of unlimited access — then fail closed to FREE.
SUBSCRIPTION_GRACE_DAYS = int(os.environ.get("SUBSCRIPTION_GRACE_DAYS", "3"))


def _as_aware_utc(dt):
    """Normalize a Mongo/ISO datetime to an aware UTC datetime, or None."""
    if not dt:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def get_user_tier(db, user_id: str) -> Tier:
    """
    Resolve a user's effective tier. Falls back to FREE if no active
    subscription record exists, or if a paid subscription has lapsed
    (past_due beyond grace period, or canceled).
    """
    sub = await db.subscriptions.find_one({"user_id": user_id})
    if not sub:
        return Tier.FREE

    status = sub.get("status", "active")
    if status not in ("active", "trialing"):
        return Tier.FREE

    now = datetime.now(timezone.utc)
    period_end = _as_aware_utc(sub.get("current_period_end"))
    if period_end is not None:
        # Motor returns datetimes tz-naive (stored as UTC); the webhook writes
        # them tz-aware. Normalizing (above) avoids a naive-vs-aware TypeError
        # that would otherwise blow up every gated route + billing/status.
        if period_end < now:
            return Tier.FREE
    else:
        # No resolvable period end. Rather than grant paid access indefinitely,
        # allow a short grace window measured from the record's last update,
        # then fail closed. If we can't even establish an anchor, downgrade now.
        anchor = _as_aware_utc(sub.get("updated_at") or sub.get("created_at"))
        if anchor is None or now > anchor + timedelta(days=SUBSCRIPTION_GRACE_DAYS):
            return Tier.FREE

    return Tier(sub.get("tier", Tier.FREE))


async def check_feature_flag(db, user_id: str, feature: str) -> bool:
    """For boolean features (sms_reminders, calendar_events, etc.)"""
    tier = await get_user_tier(db, user_id)
    limits = get_tier_limits(tier)
    return bool(limits.get(feature, False))


async def check_and_increment_usage(db, user_id: str, feature: str) -> tuple[bool, int, Optional[int]]:
    """
    For metered features (ai_screenshot_import, pdf_exports_per_month, etc).
    Returns (allowed, current_count, limit).
    Increments the counter ONLY if allowed — call this right before doing
    the expensive/costly work, not after, so failed requests don't burn quota.
    """
    tier = await get_user_tier(db, user_id)
    limits = get_tier_limits(tier)
    limit = limits.get(feature)

    # None = unlimited
    if limit is None:
        await db.usage_counters.update_one(
            {"user_id": user_id, "feature": feature, "period": _current_period()},
            {"$inc": {"count": 1}},
            upsert=True,
        )
        return True, 0, None

    # 0 or False = fully blocked on this tier
    if not limit:
        return False, 0, limit

    period = _current_period()
    doc = await db.usage_counters.find_one(
        {"user_id": user_id, "feature": feature, "period": period}
    )
    current = doc["count"] if doc else 0

    if current >= limit:
        return False, current, limit

    await db.usage_counters.update_one(
        {"user_id": user_id, "feature": feature, "period": period},
        {"$inc": {"count": 1}},
        upsert=True,
    )
    return True, current + 1, limit


async def get_usage_summary(db, user_id: str) -> dict:
    """Returns current usage + limits for all metered features — for the UI."""
    tier = await get_user_tier(db, user_id)
    limits = get_tier_limits(tier)
    period = _current_period()

    summary = {"tier": tier.value}
    for feature in METERED_FEATURES:
        doc = await db.usage_counters.find_one(
            {"user_id": user_id, "feature": feature, "period": period}
        )
        summary[feature] = {
            "used": doc["count"] if doc else 0,
            "limit": limits.get(feature),
        }
    return summary


# ═══════════════════════════════════════════════════════════════════════
# GATE HELPERS — call these as the first line inside your route body.
# This is simpler and more reliable than nested FastAPI dependencies
# (which get awkward when a dependency itself needs another dependency's
# result). Pattern:
#
#   @api.post("/calendar/events")
#   async def create_event(payload: EventIn, user=Depends(get_current_user)):
#       await gate_feature(db, user["id"], "calendar_events")
#       ... rest of route ...
#
#   @api.post("/import/screenshot")
#   async def import_screenshot(user=Depends(get_current_user)):
#       await gate_metered(db, user["id"], "ai_screenshot_import")
#       ... rest of route (the expensive Gemini call etc.) ...
#
# Both raise HTTPException(402) automatically if blocked, so you don't
# need to handle the False case yourself — just call and continue.
# ═══════════════════════════════════════════════════════════════════════

async def gate_feature(db, user_id: str, feature: str) -> None:
    """Raises 402 if this boolean feature isn't available on the user's tier."""
    allowed = await check_feature_flag(db, user_id, feature)
    if not allowed:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "upgrade_required",
                "feature": feature,
                "message": f"This feature requires a paid plan. Upgrade to unlock {feature.replace('_', ' ')}.",
            },
        )


async def gate_metered(db, user_id: str, feature: str) -> None:
    """
    Raises 402 if this month's quota is used up; otherwise increments the
    counter and returns. Call this BEFORE the expensive operation (Gemini
    call, PDF render, etc.) so failed/blocked requests don't burn quota.
    """
    allowed, used, limit = await check_and_increment_usage(db, user_id, feature)
    if not allowed:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "quota_exceeded",
                "feature": feature,
                "used": used,
                "limit": limit,
                "message": f"You've used {used}/{limit} {feature.replace('_', ' ')} this month. Upgrade for more.",
            },
        )


async def gate_claimant_limit(db, user_id: str) -> None:
    """Call before creating a new claimant profile."""
    tier = await get_user_tier(db, user_id)
    limits = get_tier_limits(tier)
    max_claimants = limits.get("max_claimants")
    if max_claimants is None:
        return
    current = await db.profiles.count_documents({"user_id": user_id})
    if current >= max_claimants:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "upgrade_required",
                "feature": "max_claimants",
                "message": f"Your plan allows {max_claimants} claimant profile(s). Upgrade to add more.",
            },
        )