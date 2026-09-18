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

    purge_date = (now + timedelta(days=ACCOUNT_PURGE_GRACE_DAYS)).strftime("%B %d, %Y")
    try:
        await send_email(
            user.get("email", ""),
            "Your Illinois UI Tracker account has been scheduled for deletion",
            _reminder_html(
                "Account deletion scheduled",
                f"""<p>We received your request to delete your Illinois UI Tracker account.</p>
                <p>Your account and all associated data — including your profile, benefit weeks,
                work-search contacts, calendar events, documents, and history — will be
                <strong>permanently deleted on {purge_date}</strong>.</p>
                <p>If you changed your mind, please contact support before that date and we can
                cancel the deletion.</p>
                <p style="color:#71717A;font-size:13px;">This action was initiated from your
                account settings. If you did not request this, contact support immediately.</p>""",
            ),
        )
    except Exception as exc:
        logging.warning(f"Deletion confirmation email failed for {user.get('email')}: {exc}")

    return {
        "ok": True,
        "purge_after": (now + timedelta(days=ACCOUNT_PURGE_GRACE_DAYS)).isoformat(),
    }


@router.post("/account/gdpr-erasure")
async def gdpr_erasure(body: DeleteAccountIn, user=Depends(get_current_user)):
    """
    GDPR Right-to-Erasure: immediately and permanently delete all data associated
    with the authenticated user.  Unlike the soft-delete route this is irreversible
    and takes effect at once — no grace period, no recovery.

    Requires the same triple confirmation as /account/delete (email, full name,
    checkbox) so that an accidental tap cannot trigger it.
    """
    if not body.confirm:
        raise HTTPException(status_code=400, detail="You must check the confirmation box.")

    if body.email.strip().lower() != (user.get("email") or "").lower():
        raise HTTPException(status_code=400, detail="The email you entered does not match your account.")

    profile = await db.profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    expected_name = ""
    if profile:
        expected_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()

    def _norm(s: str) -> str:
        return " ".join((s or "").split()).lower()

    if not expected_name or _norm(body.confirm_name) != _norm(expected_name):
        raise HTTPException(status_code=400, detail="The name you entered does not match your profile.")

    # Write an audit entry BEFORE the purge — the audit_log row itself will be
    # deleted by _purge_user_everywhere, but the admin_audit_log is retained.
    await log_audit(
        user["id"], "GDPR_ERASURE", "account", user["id"],
        "GDPR right-to-erasure: immediate hard-delete of all user data",
    )

    user_email = user.get("email", "")
    counts = await _purge_user_everywhere(user["id"], user_email)
    logging.info(f"GDPR erasure for {user_email}: {counts}")

    try:
        await send_email(
            user_email,
            "Your Illinois UI Tracker data has been permanently deleted",
            _reminder_html(
                "Data erasure complete",
                """<p>Your Illinois UI Tracker account and all associated data have been
                <strong>permanently and immediately deleted</strong> per your GDPR
                right-to-erasure request.</p>
                <p>This includes your profile, benefit weeks, work-search contacts,
                calendar events, documents, and full account history.
                <strong>This action is irreversible.</strong></p>
                <p>You may create a new account at any time using the same email address.</p>
                <p style="color:#71717A;font-size:13px;">If you did not initiate this request,
                please contact support — your data has already been removed and cannot be
                restored.</p>""",
            ),
        )
    except Exception as exc:
        logging.warning(f"GDPR erasure confirmation email failed for {user_email}: {exc}")

    return {"ok": True, "erased": counts}
