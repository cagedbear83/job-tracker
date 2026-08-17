# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403
from core import _reminder_html

router = APIRouter()



@router.get("/admin/users")
async def admin_list_users(admin=Depends(require_admin)):
    users = (
        await db.users.find({}, {"_id": 0, "password_hash": 0})
        .sort("created_at", -1)
        .to_list(500)
    )
    for u in users:
        u["claimants_count"] = await db.profiles.count_documents({"user_id": u["id"]})
        u["weeks_count"] = await db.benefit_weeks.count_documents({"user_id": u["id"]})
        u["contacts_count"] = await db.contacts.count_documents({"user_id": u["id"]})
    return users



@router.get("/admin/users/{uid}")
async def admin_user_detail(uid: str, admin=Depends(require_admin)):
    user = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    claimants = await db.profiles.find({"user_id": uid}, {"_id": 0}).to_list(100)
    weeks = (
        await db.benefit_weeks.find({"user_id": uid}, {"_id": 0})
        .sort("week_start", -1)
        .to_list(500)
    )
    for w in weeks:
        w["contact_count"] = await db.contacts.count_documents({"benefit_week_id": w["id"]})
    return {"user": user, "claimants": claimants, "weeks": weeks}



@router.get("/admin/email-events")
async def admin_email_events(admin=Depends(require_admin)):
    items = await db.email_events.find({}, {"_id": 0}).sort("received_at", -1).to_list(500)
    for it in items:
        if isinstance(it.get("received_at"), datetime):
            it["received_at"] = it["received_at"].isoformat()
    return items



@router.post("/admin/invites/bulk")
async def bulk_invite(body: BulkInviteIn, admin=Depends(require_admin)):
    reader = csv.DictReader(io.StringIO(body.csv_text))
    created, skipped = [], []
    for row in reader:
        lc = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        email = lc.get("email", "")
        if not email or "@" not in email:
            skipped.append({"row": row, "reason": "invalid email"})
            continue
        if await db.users.find_one({"email": email.lower()}):
            skipped.append({"email": email, "reason": "already a user"})
            continue
        if await db.invites.find_one({"email": email.lower(), "used": False}):
            skipped.append({"email": email, "reason": "pending invite exists"})
            continue
        code = secrets.token_urlsafe(12)
        doc = {
            "code": code,
            "email": email.lower(),
            "claimant_label": lc.get("claimant_label") or lc.get("label") or "Primary",
            "note": lc.get("note") or body.note,
            "created_by": admin["id"],
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=14),
            "used": False,
            "used_at": None,
        }
        await db.invites.insert_one(doc)
        link = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{code}"
        await send_email(
            email,
            "You're invited to Illinois UI Tracker",
            _reminder_html(
                "You're invited",
                f"<p>A case worker invited you. <a href='{link}'>Accept invite</a></p><p style='font-size:11px; color:#52525B; word-break:break-all;'>{link}</p>",
            ),
        )
        created.append({"email": email, "code": code, "invite_link": link})
    await log_audit(admin["id"], "INVITE_BULK", "invite", None, f"Created {len(created)}, skipped {len(skipped)}")
    return {"created": created, "skipped": skipped}



# ============== Integration Status (Admin) ==============
@router.get("/admin/integrations/status")
async def integrations_status(admin=Depends(require_admin)):
    has_mailgun = bool(os.environ.get("MAILGUN_API_KEY"))
    has_clicksend = bool(
        os.environ.get("CLICKSEND_USERNAME")
        and os.environ.get("CLICKSEND_API_KEY")
        and os.environ.get("CLICKSEND_FROM_NUMBER")
    )
    return {
        "mailgun": {
            "configured": has_mailgun,
            "from": os.environ.get("MAILGUN_FROM", ""),
            "verified_domain": os.environ.get("MAILGUN_VERIFIED_DOMAIN", ""),
            "fallback_from": os.environ.get("MAILGUN_FALLBACK_FROM", "onboarding@mailgun.com"),
            "dns_records_url": "https://app.mailgun.com/mg/sending/domains",
        },
        "clicksend": {
            "configured": has_clicksend,
            "from_number": os.environ.get("CLICKSEND_FROM_NUMBER", ""),
        },
    }
