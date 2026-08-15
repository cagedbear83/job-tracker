# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403
from core import _parse_mailgun_webhook, _verify_mailgun_signature

router = APIRouter()



@router.post("/webhooks/mailgun")
async def mailgun_webhook(request: Request):
    payload = await _parse_mailgun_webhook(request)
    _verify_mailgun_signature(payload)
    data = payload.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    event_type = data.get("event") or payload.get("type", "")
    to_emails = (
        data.get("recipient") or data.get("recipients")
        or data.get("message", {}).get("headers", {}).get("to") or []
    )
    if isinstance(to_emails, str):
        if "," in to_emails:
            to_emails = [addr.strip() for addr in to_emails.split(",") if addr.strip()]
        else:
            to_emails = [to_emails.strip()]
    await db.email_events.insert_one({
        "id": str(uuid.uuid4()),
        "type": event_type,
        "to": to_emails,
        "received_at": datetime.now(timezone.utc),
        "raw": data,
    })
    if event_type in ("email.bounced", "email.complained", "bounced", "complained", "complaint"):
        for addr in to_emails:
            await db.profiles.update_many(
                {"reminder_email": addr},
                {"$set": {"reminders_enabled": False, "email_bounced": True, "email_bounced_at": datetime.now(timezone.utc).isoformat()}},
            )
            users_with_email = await db.users.find(
                {"email": addr.lower() if isinstance(addr, str) else ""}, {"_id": 0, "id": 1}
            ).to_list(20)
            for u in users_with_email:
                await db.profiles.update_many(
                    {"user_id": u["id"], "reminder_email": ""},
                    {"$set": {"reminders_enabled": False, "email_bounced": True}},
                )
    return {"ok": True}



@router.post("/webhooks/stripe")
async def stripe_webhook_route(request: Request):
    # NOTE: intentionally no auth dependency — Stripe calls this directly
    # and authenticity is verified via signature in handle_stripe_webhook,
    # not via JWT.
    return await billing_logic.handle_stripe_webhook(db, request)
