# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403
from core import _check_account_lockout, _clear_failed_logins, _record_failed_login

router = APIRouter()



# ============== Auth Endpoints ==============
@router.post("/auth/register", response_model=RegisterOut)
@rate_limit(RATE_LIMIT_REGISTER)
async def register(request: Request, body: RegisterIn):
    # Server-side password policy check (mirrors frontend validation)
    policy_error = validate_password_policy(body.password, body.email, body.name)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    uid = str(uuid.uuid4())
    user_doc = {
        "id": uid,
        "email": email,
        "name": body.name,
        "password_hash": hash_password(body.password),
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)

    # Store the registration details using the canonical profile schema
    # (ProfileIn) so the Profile page, claimant list, and IDES reports all read
    # them back. Writing ad-hoc keys here (full_name / zip / is_primary) is what
    # caused registration data to silently not appear on the profile.
    pid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    profile_doc = {
        "id": pid,
        "user_id": uid,
        "updated_at": now_iso,
        "created_at": now_iso,
        "label": "Primary",
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
        "sms_enabled": False,
        # Not part of ProfileIn, but collected at registration — keep it so the
        # data isn't lost. Profile edits use $set, so this survives updates.
        "date_of_birth": body.dob,
    }
    await db.profiles.insert_one(profile_doc)
    # Make this the active claimant explicitly (rather than relying on the
    # first-profile fallback), matching how create_claimant behaves.
    await db.users.update_one(
        {"id": uid}, {"$set": {"active_claimant_id": pid}}
    )

    verification_token = secrets.token_urlsafe(32)
    await db.users.update_one(
        {"id": uid},
        {
            "$set": {
                "email_verified": False,
                "verification_token": verification_token,
                "verification_token_expires": datetime.now(timezone.utc)
                + timedelta(hours=24),
            }
        },
    )
    # Point the verification link at the BACKEND, not the SPA. The backend
    # verifies the token and 302-redirects the browser to the frontend. This
    # removes the cross-origin XHR the SPA used to make (no CORS surface) and
    # replaces an XHR burst with a single top-level navigation, which is far
    # less likely to trip edge rate limiting.
    backend_base = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/") or str(
        request.base_url
    ).rstrip("/")
    verify_url = f"{backend_base}/api/auth/verify-email?token={verification_token}"
    await send_email(
        email,
        "Verify your Illinois UI Tracker email",
        f"""
        <p>Thanks for signing up. Please verify your email address:</p>
        <a href="{verify_url}" style="background:#0033A0;color:#fff;padding:12px 24px;text-decoration:none;font-weight:bold;display:inline-block;">
            Verify Email Address
        </a>
        <p>This link expires in 24 hours.</p>
        """,
    )

    await log_audit(uid, "REGISTER", "user", uid, f"Account created: {email}")
    return RegisterOut(
        message="Account created. Please check your email to verify your address before logging in.",
        user=UserPublic(id=uid, email=email, name=body.name, role="user"),
    )



@router.post("/auth/login", response_model=AuthOut)
@rate_limit(RATE_LIMIT_LOGIN)
async def login(request: Request, body: LoginIn):
    email = body.email.lower()

    # Check lockout BEFORE touching the password — avoids timing oracle
    await _check_account_lockout(email)

    user = await db.users.find_one({"email": email})

    # Always verify password (even if user is None via dummy hash) to prevent
    # timing-based user enumeration
    dummy_hash = "$2b$12$invalidhashfortimingprotectionpurposesonly000000000000"
    stored_hash = user["password_hash"] if user else dummy_hash
    password_ok = verify_password(body.password, stored_hash)

    if not user or not password_ok:
        if user:
            # Only record failed attempts for real accounts
            await _record_failed_login(email)
            rec = await db.login_attempts.find_one({"email": email})
            attempts = rec.get("attempts", 0) if rec else 0
            remaining_attempts = max(0, LOGIN_MAX_ATTEMPTS - attempts)
            if remaining_attempts > 0:
                detail = f"Invalid email or password. {remaining_attempts} attempt(s) remaining before temporary lockout."
            else:
                detail = f"Account temporarily locked for {LOCKOUT_DURATION_MINUTES} minutes due to too many failed attempts."
            await log_audit(
                user["id"], "LOGIN_FAIL", "user", user["id"],
                f"Failed login attempt #{attempts} from {request.client.host if request.client else 'unknown'}"
            )
        else:
            detail = "Invalid email or password."
        raise HTTPException(status_code=401, detail=detail)

    if user.get("deleted"):
        raise HTTPException(
            status_code=403,
            detail="This account has been deleted.",
        )

    if not user.get("email_verified", False):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email address before logging in.",
        )

    # Successful login — clear any failed attempt record
    await _clear_failed_logins(email)

    token = create_token(user["id"], user["email"])
    await log_audit(user["id"], "LOGIN", "user", user["id"], "Login successful")
    return AuthOut(
        token=token,
        user=UserPublic(
            id=user["id"],
            email=user["email"],
            name=user.get("name", ""),
            role=user.get("role", "user"),
        ),
    )



@router.get("/auth/verify-email")
async def verify_email(token: str):
    # This route is opened directly by the browser via the emailed link, so it
    # responds with a redirect to the frontend login page rather than JSON.
    # Because it's a top-level navigation (not a cross-origin XHR), CORS never
    # applies here.
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")

    def _to_login(params: str) -> RedirectResponse:
        # 303 forces the browser to follow with a GET regardless of method.
        return RedirectResponse(url=f"{frontend}/login?{params}", status_code=303)

    user = await db.users.find_one({"verification_token": token})
    if not user:
        return _to_login("verify_error=invalid")
    expires = user.get("verification_token_expires")
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires and expires.tzinfo is None:
        # Mongo returns datetimes tz-naive (stored as UTC); make it aware
        # before comparing, matching the token-expiry handling elsewhere.
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and datetime.now(timezone.utc) > expires:
        return _to_login("verify_error=expired")
    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {"email_verified": True},
            "$unset": {"verification_token": "", "verification_token_expires": ""},
        },
    )
    return _to_login("verified=1")



@router.post("/auth/logout")
async def logout(user=Depends(get_current_user)):
    await log_audit(user["id"], "LOGOUT", "user", user["id"], "Logout")
    return {"ok": True}



@router.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return UserPublic(
        id=user["id"],
        email=user["email"],
        name=user.get("name", ""),
        role=user.get("role", "user"),
    )



# ============== Password Reset ==============
@router.post("/auth/forgot-password")
@rate_limit(RATE_LIMIT_FORGOT)
async def forgot_password(request: Request, body: ForgotPwIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if user:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.password_resets.insert_one(
            {
                "token": token,
                "user_id": user["id"],
                "expires_at": expires,
                "used": False,
                "created_at": datetime.now(timezone.utc),
            }
        )
        link = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={token}"
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="color-scheme" content="light dark">
          <meta name="supported-color-schemes" content="light dark">
          <style>
            @media (prefers-color-scheme: dark) {{
              .email-bg   {{ background-color: #1a1a1a !important; }}
              .email-body {{ background-color: #2a2a2a !important; border-color: #444 !important; }}
              .email-text {{ color: #e4e4e7 !important; }}
              .email-muted {{ color: #a1a1aa !important; }}
            }}
          </style>
        </head>
        <body style="margin:0; padding:16px; background-color:#f4f4f5;" class="email-bg">
          <div style="font-family:'IBM Plex Sans',Arial,sans-serif; max-width:560px; margin:auto;">
            <div style="background:#0033A0; padding:16px 24px; border-radius:4px 4px 0 0;">
              <div style="display:flex; align-items:center; gap:12px;">
                <div style="background:#fff; color:#0033A0; font-weight:900; font-size:18px; width:36px; height:36px; display:inline-flex; align-items:center; justify-content:center; border-radius:4px; font-family:'Chivo',Arial,sans-serif;">IL</div>
                <div>
                  <div style="color:#fff; font-family:'Chivo',Arial,sans-serif; font-weight:900; font-size:16px; letter-spacing:-0.01em;">Illinois UI Job Search Tracker</div>
                  <div style="color:#93afd4; font-size:11px; letter-spacing:0.08em; text-transform:uppercase;">Work Search Compliance</div>
                </div>
              </div>
            </div>
            <div style="background:#ffffff; border:1px solid #D4D4D8; border-top:none; border-radius:0 0 4px 4px; padding:24px;" class="email-body">
              <h2 style="margin:0 0 16px; font-family:'Chivo',Arial,sans-serif; font-weight:900; color:#09090B;" class="email-text">Password Reset</h2>
              <p style="color:#09090B;" class="email-text">You requested a password reset for your Illinois UI Job Search Tracker account.</p>
              <div style="margin:24px 0;">
                <a href="{link}" style="display:inline-block; background:#0033A0; color:#ffffff; padding:12px 24px; text-decoration:none; font-weight:600; font-size:14px; border-radius:2px;">Reset My Password</a>
              </div>
              <hr style="border:none; border-top:1px solid #e4e4e7; margin:20px 0;">
              <p style="font-size:12px; color:#52525B;" class="email-muted">This link expires in 1 hour. If you didn't request this, ignore this email.</p>
              <p style="font-size:12px; color:#52525B; word-break:break-all;" class="email-muted">{link}</p>
            </div>
          </div>
        </body>
        </html>
        """
        sent = await send_email(email, "Reset your Illinois UI Tracker password", html)
        await log_audit(
            user["id"], "FORGOT_PW", "user", user["id"],
            f"Reset link sent (mailgun={'ok' if sent else 'fail'})",
        )
    return {"ok": True, "message": "If that email exists, a reset link has been sent."}



@router.post("/auth/reset-password")
async def reset_password(body: ResetPwIn):
    # Server-side password policy check on reset too
    policy_error = validate_password_policy(body.password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    rec = await db.password_resets.find_one({"token": body.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or used token")
    exp = rec["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        raise HTTPException(status_code=400, detail="Token expired")
    await db.users.update_one(
        {"id": rec["user_id"]},
        {"$set": {"password_hash": hash_password(body.password)}},
    )
    await db.password_resets.update_one({"token": body.token}, {"$set": {"used": True}})
    # Also clear any lockout on successful password reset
    user = await db.users.find_one({"id": rec["user_id"]}, {"_id": 0, "email": 1})
    if user:
        await _clear_failed_logins(user["email"])
    await log_audit(
        rec["user_id"], "RESET_PW", "user", rec["user_id"], "Password reset via email link"
    )
    return {"ok": True}
