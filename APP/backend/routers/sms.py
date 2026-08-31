# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



@router.post("/sms/send-otp")
async def sms_send_otp(body: OtpSendIn, user=Depends(get_current_user)):
    await sub.gate_feature(db, user["id"], "sms_reminders")
    c = await db.profiles.find_one({"id": body.claimant_id, "user_id": user["id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Claimant not found")
    phone = body.phone.strip()
    if not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Phone must be E.164 (e.g. +13125550100)")
    import random
    code = f"{random.randint(0, 999999):06d}"
    await db.otp_codes.insert_one({
        "claimant_id": body.claimant_id,
        "user_id": user["id"],
        "phone": phone,
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    msg = f"Illinois UI Tracker verification code: {code} (expires in 10 minutes). Reply STOP to opt out, HELP for help."
    sent, reason = await send_sms_rate_limited(phone, msg, body.claimant_id)
    await log_audit(user["id"], "OTP_SEND", "claimant", body.claimant_id, f"OTP to {phone}: {'sent' if sent else reason}")
    if not sent:
        raise HTTPException(
            status_code=502,
            detail=f"Could not send SMS ({reason}). Check that ClickSend is configured and the account has SMS credit.",
        )
    return {"ok": True, "expires_in_minutes": 10}



@router.post("/sms/verify-otp")
async def sms_verify_otp(body: OtpVerifyIn, user=Depends(get_current_user)):
    rec = await db.otp_codes.find_one(
        {"claimant_id": body.claimant_id, "user_id": user["id"], "used": False},
        sort=[("created_at", -1)],
    )
    if not rec:
        raise HTTPException(status_code=400, detail="No active OTP found. Request a new code.")
    exp = rec["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        raise HTTPException(status_code=400, detail="Code expired. Request a new one.")
    if rec["code"] != body.code.strip():
        raise HTTPException(status_code=400, detail="Incorrect code")
    await db.otp_codes.update_one({"_id": rec["_id"]}, {"$set": {"used": True}})
    await db.profiles.update_one(
        {"id": body.claimant_id, "user_id": user["id"]},
        {"$set": {"sms_verified": True, "sms_phone": rec["phone"], "sms_verified_at": datetime.now(timezone.utc).isoformat()}},
    )
    await log_audit(user["id"], "OTP_VERIFY", "claimant", body.claimant_id, f"Phone {rec['phone']} verified")
    return {"ok": True, "phone": rec["phone"]}
