# Auth routes.
#
# Clerk owns identity now — sign-up, sign-in, email verification, password
# reset, MFA, and the Google / Apple providers all happen client-side against
# Clerk and never touch this server. What used to live here and is now gone:
#
#   POST /auth/register         -> Clerk <SignUp/>
#   POST /auth/login            -> Clerk <SignIn/>
#   GET  /auth/verify-email     -> Clerk
#   POST /auth/forgot-password  -> Clerk
#   POST /auth/reset-password   -> Clerk
#   POST /auth/refresh          -> Clerk (short-lived tokens, minted per request)
#   POST /auth/logout           -> Clerk signOut()
#
# Along with them went the refresh-token rotation table, the httpOnly refresh
# cookie, bcrypt password hashing, the password policy, and the login-attempt
# lockout. See clerk_auth.py for what replaced the verification path.
#
# What remains is the part Clerk cannot know about: this app's own view of the
# user (roles, tier, claimant profile) and the onboarding step that captures
# the claimant details registration used to collect.
from core import *  # noqa: F401,F403
from core import _seed_certification_events

router = APIRouter()


@router.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    # get_current_user provisions the local user document on first contact,
    # so reaching this line always means a row exists.
    return UserPublic(
        id=user["id"],
        email=user["email"],
        name=user.get("name", ""),
        role=user.get("role", "user"),
        platform_role=user.get("platform_role", "user"),
        needs_onboarding=not user.get("active_claimant_id"),
    )


@router.post("/auth/onboarding")
async def complete_onboarding(body: OnboardingIn, user=Depends(get_current_user)):
    """Create the claimant profile for a freshly signed-up account.

    Lifted from the old POST /auth/register, minus account creation. Runs once:
    if the account already has an active claimant, this is a no-op rather than
    a second profile, so a double-submit or a stale tab cannot fork the user's
    records.
    """
    uid = user["id"]

    if user.get("active_claimant_id"):
        existing = await db.profiles.find_one(
            {"id": user["active_claimant_id"], "user_id": uid}, {"_id": 0}
        )
        if existing:
            return existing

    pid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # Canonical profile schema (ProfileIn) so the Profile page, claimant list,
    # and IDES reports all read these back. Writing ad-hoc keys here is what
    # previously caused registration data to silently not appear on the profile.
    profile_doc = {
        "id": pid,
        "user_id": uid,
        "updated_at": now_iso,
        "created_at": now_iso,
        # An invitation can pre-name the claimant; fall back to "Primary".
        "label": user.get("pending_claimant_label") or "Primary",
        "first_name": body.first_name,
        "last_name": body.last_name,
        "middle_initial": "",
        "claimant_id": body.claimant_id or "",
        "address": body.address,
        "city": body.city,
        "state": "IL",
        "zip_code": body.zip,
        "phone": body.phone,
        "occupation": "",
        "reminders_enabled": True,
        "reminder_email": "",
        # sms_enabled records consent only — no SMS is sent until the number is
        # verified via OTP (sets sms_phone + sms_verified; see routers/sms.py),
        # so an opted-in-but-unverified profile never receives messages.
        "sms_enabled": body.sms_opt_in,
        # Consent timestamp, kept alongside the SMS_OPT_IN audit entry below
        # for carrier / TCPA recordkeeping.
        "sms_opt_in_at": now_iso if body.sms_opt_in else None,
        # Not part of ProfileIn but collected here — profile edits use $set,
        # so this survives later updates.
        "date_of_birth": body.dob,
    }
    await db.profiles.insert_one(profile_doc)

    # Set the active claimant explicitly rather than relying on the
    # first-profile fallback, matching how create_claimant behaves.
    await db.users.update_one(
        {"id": uid},
        {"$set": {"active_claimant_id": pid}, "$unset": {"pending_claimant_label": ""}},
    )

    if body.knows_next_cert_date == "yes" and body.next_certification_date:
        seeded = await _seed_certification_events(
            uid, pid, body.next_certification_date
        )
        if seeded:
            await log_audit(
                uid,
                "CALENDAR_SEED",
                "claimant",
                pid,
                f"Seeded {seeded} bi-weekly certification events starting {body.next_certification_date}",
            )

    if body.sms_opt_in:
        await log_audit(
            uid,
            "SMS_OPT_IN",
            "claimant",
            pid,
            f"Opted in to SMS reminders at onboarding (phone: {body.phone or 'not provided'})",
        )

    await log_audit(uid, "ONBOARDING", "user", uid, f"Profile completed: {user['email']}")

    profile_doc.pop("_id", None)
    return profile_doc
