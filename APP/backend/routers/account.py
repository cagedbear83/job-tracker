# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



@router.post("/account/delete")
async def delete_account(body: DeleteAccountIn, user=Depends(get_current_user)):
    """
    Soft-delete the authenticated user's account. Requires the user to re-type
    their login email, their profile name, and check the confirmation box. The
    account is deactivated immediately (all tokens rejected) and its data is
    hard-purged after ACCOUNT_PURGE_GRACE_DAYS.
    """
    if not body.confirm:
        raise HTTPException(status_code=400, detail="You must check the confirmation box.")

    # Verify the typed email matches the account email (defense in depth — the
    # deletion targets the authenticated user regardless).
    if body.email.strip().lower() != (user.get("email") or "").lower():
        raise HTTPException(status_code=400, detail="The email you entered does not match your account.")

    # Verify the typed name matches the profile's first + last name.
    profile = await db.profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    expected_name = ""
    if profile:
        expected_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()

    def _norm(s: str) -> str:
        return " ".join((s or "").split()).lower()

    if not expected_name or _norm(body.confirm_name) != _norm(expected_name):
        raise HTTPException(status_code=400, detail="The name you entered does not match your profile.")

    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "deleted": True,
            "deletion_requested_at": now,
            "purge_after": now + timedelta(days=ACCOUNT_PURGE_GRACE_DAYS),
            # Rotate the session marker so any outstanding token is dead.
            "active_claimant_id": None,
        }},
    )
    await log_audit(
        user["id"], "DELETE", "account", user["id"],
        f"Account soft-deleted; scheduled purge after {ACCOUNT_PURGE_GRACE_DAYS} days",
    )
    return {
        "ok": True,
        "purge_after": (now + timedelta(days=ACCOUNT_PURGE_GRACE_DAYS)).isoformat(),
    }
