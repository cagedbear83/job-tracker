# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



# ============== Invite Codes (Admin) ==============
@router.post("/admin/invites")
async def create_invite(body: InviteCreate, admin=Depends(require_admin)):
    code = secrets.token_urlsafe(12)
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="A user with that email already exists")
    doc = {
        "code": code,
        "email": body.email.lower(),
        "claimant_label": body.claimant_label or "Primary",
        "note": body.note,
        "created_by": admin["id"],
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=14),
        "used": False,
        "used_at": None,
    }
    await db.invites.insert_one(doc)
    await log_audit(admin["id"], "INVITE_CREATE", "invite", code, f"Invite for {body.email}")
    invite_link = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{code}"
    html = f"""
    <div style="font-family:'IBM Plex Sans',Arial,sans-serif; max-width:560px; margin:auto; color:#09090B;">
      <div style="background:#0033A0; color:#fff; padding:18px 24px;">
        <h2 style="margin:0; font-family:'Chivo',Arial,sans-serif; font-weight:900;">You're invited</h2>
      </div>
      <div style="border:1px solid #D4D4D8; border-top:none; padding:24px;">
        <p>A case worker has invited you to the Illinois UI Job Search Tracker.</p>
        {f'<p style="background:#F4F4F5; padding:12px; border-left:3px solid #0033A0;">{body.note}</p>' if body.note else ""}
        <p><a href="{invite_link}" style="display:inline-block; background:#0033A0; color:#fff; padding:12px 20px; text-decoration:none; font-weight:600;">Accept Invite</a></p>
        <p style="font-size:12px; color:#52525B;">Link expires in 14 days.</p>
        <p style="font-size:12px; color:#52525B; word-break:break-all;">{invite_link}</p>
      </div>
    </div>
    """
    await send_email(body.email, "You're invited to Illinois UI Tracker", html)
    doc.pop("_id", None)
    doc["invite_link"] = invite_link
    return doc



@router.get("/admin/invites")
async def list_invites(admin=Depends(require_admin)):
    items = await db.invites.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for it in items:
        it["invite_link"] = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{it['code']}"
    return items



@router.delete("/admin/invites/{code}")
async def revoke_invite(code: str, admin=Depends(require_admin)):
    res = await db.invites.delete_one({"code": code})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(admin["id"], "INVITE_REVOKE", "invite", code, "Invite revoked")
    return {"ok": True}



@router.get("/invite/{code}")
async def get_invite(code: str):
    inv = await db.invites.find_one({"code": code}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv.get("used"):
        raise HTTPException(status_code=400, detail="Invite already used")
    exp = inv.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and datetime.now(timezone.utc) > exp:
        raise HTTPException(status_code=400, detail="Invite expired")
    return {
        "email": inv["email"],
        "claimant_label": inv.get("claimant_label", "Primary"),
        "note": inv.get("note", ""),
    }



@router.post("/invite/redeem")
async def redeem_invite(body: InviteRedeem):
    # Password policy check on invite redemption too
    policy_error = validate_password_policy(body.password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    inv = await db.invites.find_one({"code": body.code})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv.get("used"):
        raise HTTPException(status_code=400, detail="Invite already used")
    exp = inv.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and datetime.now(timezone.utc) > exp:
        raise HTTPException(status_code=400, detail="Invite expired")
    if await db.users.find_one({"email": inv["email"]}):
        raise HTTPException(status_code=400, detail="Account already exists with this email")
    uid = str(uuid.uuid4())
    await db.users.insert_one({
        "id": uid,
        "email": inv["email"],
        "name": body.name,
        "password_hash": hash_password(body.password),
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "invited_by": inv.get("created_by"),
    })
    pid = str(uuid.uuid4())
    await db.profiles.insert_one({
        "id": pid,
        "user_id": uid,
        "label": inv.get("claimant_label", "Primary"),
        "first_name": "",
        "last_name": "",
        "middle_initial": "",
        "claimant_id": "",
        "address": "",
        "city": "",
        "state": "IL",
        "zip_code": "",
        "phone": "",
        "occupation": "",
        "reminders_enabled": True,
        "reminder_email": "",
        "sms_enabled": False,
        "sms_phone": "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.users.update_one({"id": uid}, {"$set": {"active_claimant_id": pid}})
    await db.invites.update_one(
        {"code": body.code},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc), "redeemed_user_id": uid}},
    )
    await log_audit(uid, "REGISTER_INVITE", "user", uid, f"Invited account created from {inv.get('created_by')}")
    token = create_token(uid, inv["email"])
    return {"token": token, "user": {"id": uid, "email": inv["email"], "name": body.name, "role": "user"}}
