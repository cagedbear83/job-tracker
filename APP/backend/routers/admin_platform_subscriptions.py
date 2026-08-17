# Ported from admin_portal/admin_subscriptions.py.
#
# Admin platform: Subscriptions module (read-only).
#
# Reads the local db.subscriptions record and, if a Stripe secret with read
# scope is configured, enriches with live Stripe status. NO writes, NO money
# movement here — comps live in admin_platform_comps.py, refunds in
# admin_platform_refunds.py.
from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from core import db
from rbac import require_staff

router = APIRouter(prefix="/admin/platform/subscriptions", tags=["admin-platform:subscriptions"])


def _stripe():
    """Return the stripe module configured for READ-only use, or None."""
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        return None
    import stripe  # local import so the app doesn't hard-depend on it here
    stripe.api_key = key
    return stripe


@router.get("/{user_id}", dependencies=[Depends(require_staff)])
async def get_subscription(user_id: str):
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    if not sub:
        return {"user_id": user_id, "tier": "free", "source": "no_record"}

    out = {"local": sub, "stripe": None}

    stripe = _stripe()
    sub_id = sub.get("stripe_subscription_id")
    if stripe and sub_id:
        try:
            s = stripe.Subscription.retrieve(sub_id)
            out["stripe"] = {
                "status": s.get("status"),
                "current_period_end": s.get("current_period_end"),
                "cancel_at_period_end": s.get("cancel_at_period_end"),
                "quantity": (s.get("items", {}).get("data", [{}])[0].get("quantity")),
            }
        except Exception as e:  # never let a Stripe read failure 500 the portal
            out["stripe_error"] = str(e)
    return out
