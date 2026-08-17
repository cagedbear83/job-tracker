"""
billing.py — Stripe checkout, webhook handling, and customer portal for
Illinois UI Job Search Tracker.

Drop into APP/backend/billing.py. Requires: pip install stripe --break-system-packages

INTEGRATION PATTERN:
This module exposes plain async LOGIC functions (no @router decorators,
no Depends). Add four thin route wrappers directly in server.py where
`get_current_user` and `db` already exist in scope:

    import billing as billing_logic

    @api.post("/billing/checkout")
    async def billing_checkout(payload: billing_logic.CheckoutRequest, user=Depends(get_current_user)):
        return await billing_logic.create_checkout_session(db, FRONTEND_URL, user, payload)

    @api.post("/billing/portal")
    async def billing_portal(user=Depends(get_current_user)):
        return await billing_logic.create_portal_session(db, FRONTEND_URL, user)

    @api.get("/billing/status")
    async def billing_status_route(user=Depends(get_current_user)):
        return await billing_logic.billing_status(db, user)

    @api.post("/webhooks/stripe")
    async def stripe_webhook_route(request: Request):
        return await billing_logic.handle_stripe_webhook(db, request)

Note the webhook route takes NO auth dependency — Stripe calls it directly
and authenticity is verified via signature, not JWT.
"""

import os
import stripe
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel

from typing import Optional
from subscription import Tier, get_checkout_line_items, get_user_tier, get_usage_summary
import Disputes as dispute_engine

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def _period_end(sub_obj) -> Optional[datetime]:
    """
    Read `current_period_end` as an aware UTC datetime across Stripe API
    versions. Older versions expose it on the Subscription object; the 2025
    ("basil") versions moved it onto the subscription items. Works with both
    dict-like webhook payloads and stripe-python objects. Returns None if it
    can't be found (caller then leaves the stored value untouched).
    """
    def _get(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    ts = _get(sub_obj, "current_period_end")
    if ts is None:
        items = _get(sub_obj, "items")
        data = _get(items, "data") if items is not None else None
        if data:
            ts = _get(data[0], "current_period_end")
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class CheckoutRequest(BaseModel):
    tier: Tier
    interval: str = "monthly"        # "monthly" or "annual"
    seats: int = 1                    # Case Worker only; ignored for Pro


# ═══════════════════════════════════════════════════════════════════════
# CHECKOUT — create a Stripe Checkout session for upgrading
# ═══════════════════════════════════════════════════════════════════════

async def create_checkout_session(db, frontend_url: str, user: dict, payload: CheckoutRequest) -> dict:
    if payload.tier == Tier.FREE:
        raise HTTPException(status_code=400, detail="Cannot checkout for the free tier")

    if payload.interval not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="interval must be 'monthly' or 'annual'")

    if payload.seats < 1:
        raise HTTPException(status_code=400, detail="seats must be at least 1")

    try:
        line_items = get_checkout_line_items(payload.tier, payload.interval, payload.seats)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Guard against unconfigured price IDs (empty env vars)
    if any(not item["price"] for item in line_items):
        raise HTTPException(
            status_code=500,
            detail="Stripe price IDs are not fully configured for this tier/interval.",
        )

    existing_sub = await db.subscriptions.find_one({"user_id": user["id"]})
    customer_id = existing_sub.get("stripe_customer_id") if existing_sub else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"user_id": user["id"]},
        )
        customer_id = customer.id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=line_items,
        mode="subscription",
        success_url=f"{frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend_url}/billing/canceled",
        metadata={
            "user_id": user["id"],
            "tier": payload.tier.value,
            "interval": payload.interval,
            "seats": str(payload.seats),
        },
    )

    return {"checkout_url": session.url}


# ═══════════════════════════════════════════════════════════════════════
# CUSTOMER PORTAL — let users manage/cancel their subscription
# ═══════════════════════════════════════════════════════════════════════

async def create_portal_session(db, frontend_url: str, user: dict) -> dict:
    sub = await db.subscriptions.find_one({"user_id": user["id"]})
    if not sub or not sub.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=sub["stripe_customer_id"],
        return_url=f"{frontend_url}/profile",
    )
    return {"portal_url": session.url}


# ═══════════════════════════════════════════════════════════════════════
# WEBHOOK — Stripe calls this on every subscription lifecycle event.
# This is the source of truth for tier state — never trust the frontend
# to tell you a user upgraded; always wait for this webhook.
# ═══════════════════════════════════════════════════════════════════════

async def handle_stripe_webhook(db, request: Request) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data["metadata"].get("user_id")
        tier = data["metadata"].get("tier", Tier.FREE.value)
        interval = data["metadata"].get("interval", "monthly")
        seats = int(data["metadata"].get("seats", "1"))
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")

        if user_id and subscription_id:
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            await db.subscriptions.update_one(
                {"user_id": user_id},
                {"$set": {
                    "user_id": user_id,
                    "tier": tier,
                    "interval": interval,
                    "seats": seats,
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "status": stripe_sub.status,
                    "current_period_end": _period_end(stripe_sub),
                    "cancel_at_period_end": stripe_sub.cancel_at_period_end,
                    "updated_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        subscription_id = data["id"]
        status = data["status"] if event_type.endswith("updated") else "canceled"

        set_fields = {
            "status": status,
            "cancel_at_period_end": data.get("cancel_at_period_end", False),
            "updated_at": datetime.now(timezone.utc),
        }
        # Only overwrite the period end if we could resolve it (its location in
        # the payload varies by Stripe API version); never crash on a KeyError.
        period_end = _period_end(data)
        if period_end is not None:
            set_fields["current_period_end"] = period_end

        await db.subscriptions.update_one(
            {"stripe_subscription_id": subscription_id},
            {"$set": set_fields},
        )

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        await db.subscriptions.update_one(
            {"stripe_customer_id": customer_id},
            {"$set": {"status": "past_due", "updated_at": datetime.now(timezone.utc)}},
        )

    # ── Dispute engine ingestion (see Disputes.py) ──────────────────────
    # Feeds the admin-platform Disputes tab (routers/admin_disputes.py).
    # charge.succeeded is the denominator for the chargeback rate;
    # charge.dispute.* are the numerator. Email alerting
    # (Disputes.check_and_alert) is NOT wired in here — see that function's
    # docstring for what it needs if someone wants to add it later.
    elif event_type == "charge.succeeded":
        await dispute_engine.record_charge(db, data["id"])

    elif event_type in (
        "charge.dispute.created", "charge.dispute.updated", "charge.dispute.closed",
    ):
        customer_id = data.get("customer") if isinstance(data.get("customer"), str) else None
        user_id = None
        if customer_id:
            sub = await db.subscriptions.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "user_id": 1})
            user_id = sub["user_id"] if sub else None
        await dispute_engine.upsert_dispute(
            db,
            {
                "id": data["id"],
                "charge_id": data.get("charge"),
                "amount_cents": data.get("amount"),
                "currency": data.get("currency", "usd"),
                "reason": data.get("reason"),
                "status": data.get("status"),
                "evidence_due_by": (data.get("evidence_details") or {}).get("due_by"),
            },
            user_id,
        )

    return {"received": True}


# ═══════════════════════════════════════════════════════════════════════
# STATUS — frontend polls this to know current tier + usage
# ═══════════════════════════════════════════════════════════════════════

async def billing_status(db, user: dict) -> dict:
    tier = await get_user_tier(db, user["id"])
    usage = await get_usage_summary(db, user["id"])
    sub = await db.subscriptions.find_one({"user_id": user["id"]}, {"_id": 0})

    return {
        "tier": tier.value,
        "usage": usage,
        "subscription": sub,
    }