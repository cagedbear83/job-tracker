# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

import clerk_auth
from routers.invites import _signup_url
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
    """Invite many claimants from a CSV, via Clerk.

    Same CSV contract as before (email, optional claimant_label / label, note),
    but each row now creates a Clerk invitation instead of a local
    `db.invites` row with a random code — see routers/invites.py.
    """
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
        try:
            invitation = clerk_auth.create_invitation(
                email=email.lower(),
                redirect_url=_signup_url(),
                claimant_label=lc.get("claimant_label") or lc.get("label") or "Primary",
                invited_by=admin["id"],
                note=lc.get("note") or body.note,
            )
        except HTTPException as e:
            # One bad row shouldn't abort the whole batch.
            skipped.append({"email": email, "reason": str(e.detail)[:200]})
            continue
        created.append({"email": email, "id": invitation.get("id")})

    await log_audit(
        admin["id"],
        "INVITE_BULK",
        "invite",
        None,
        f"Created {len(created)}, skipped {len(skipped)}",
    )
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


# ============== Caseworker Org Management ==============


@router.delete("/admin/caseworkers/{caseworker_id}/remove")
async def remove_caseworker(caseworker_id: str, admin=Depends(require_admin)):
    """
    Detach all claimants from a caseworker's org by clearing their
    `managed_by` field (and the corresponding `org_id` on the user doc).

    This does NOT delete the caseworker's own account or their claimants'
    accounts — it only orphans the relationship so those claimants show up
    as self-managed individuals.  Hard-delete of any account is a separate
    /account/delete or /account/gdpr-erasure action.
    """
    # Verify the target is actually a caseworker
    cw = await db.users.find_one({"id": caseworker_id}, {"_id": 0, "id": 1, "email": 1, "role": 1})
    if not cw:
        raise HTTPException(status_code=404, detail="Caseworker not found.")

    # Find all profiles managed by this caseworker
    managed_profiles = await db.profiles.find(
        {"managed_by": caseworker_id}, {"_id": 0, "id": 1, "user_id": 1}
    ).to_list(None)

    profile_ids = [p["id"] for p in managed_profiles]
    user_ids = list({p["user_id"] for p in managed_profiles})

    if profile_ids:
        # Clear managed_by on all profiles
        await db.profiles.update_many(
            {"managed_by": caseworker_id},
            {"$unset": {"managed_by": ""}},
        )
        # Clear org_id on corresponding user docs
        if user_ids:
            await db.users.update_many(
                {"id": {"$in": user_ids}},
                {"$unset": {"org_id": ""}},
            )

    await log_audit(
        admin["id"],
        "CASEWORKER_REMOVE",
        "user",
        caseworker_id,
        f"Detached {len(profile_ids)} claimant profile(s) from caseworker {cw.get('email', caseworker_id)}",
    )

    return {
        "ok": True,
        "caseworker_id": caseworker_id,
        "orphaned_profiles": len(profile_ids),
        "affected_user_ids": user_ids,
    }
