from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import asyncio
import csv
import hashlib
import hmac
import html
import io
import json
import logging
import os
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Literal, Optional

import bcrypt
import jwt
import pytz
import requests as http_requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware
from twilio.rest import Client as TwilioClient

# Optional production dependencies — degrade gracefully if a deploy has not
# reinstalled requirements yet, rather than crashing the whole API.
try:
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    _SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SLOWAPI_AVAILABLE = False

# ---- Error tracking (Sentry) ----
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if SENTRY_DSN and sentry_sdk is not None:
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            traces_sample_rate=float(
                os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")
            ),
            send_default_pii=False,
        )
    except Exception as e:  # pragma: no cover
        logging.warning(f"Sentry init failed: {e}")

# ---- DB ----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(
    mongo_url,
    appname=os.environ.get("MONGO_APP_NAME", "ides-job-tracker"),
    maxPoolSize=int(os.environ.get("MONGO_MAX_POOL_SIZE", "20")),
    minPoolSize=int(os.environ.get("MONGO_MIN_POOL_SIZE", "0")),
    serverSelectionTimeoutMS=int(
        os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")
    ),
    connectTimeoutMS=int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "10000")),
)
db = client[os.environ["DB_NAME"]]

# ---- App ----
app = FastAPI(title="Illinois UI Job Search Tracker")
api = APIRouter(prefix="/api")

# ---- Stripe billing (checkout, portal, webhook, status) ----
import billing as billing_logic

# ---- Subscription tier enforcement (gate_feature / gate_metered) ----
# These raise HTTP 402 when a user's plan doesn't include a feature or has
# exhausted a metered quota. gate_metered also increments the usage counter.
import subscription as sub

# ---- Rate limiting ----
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
RATE_LIMIT_LOGIN = os.environ.get("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_REGISTER = os.environ.get("RATE_LIMIT_REGISTER", "3/hour")
RATE_LIMIT_FORGOT = os.environ.get("RATE_LIMIT_FORGOT", "3/hour")
RATE_LIMIT_REMINDER_TEST = os.environ.get("RATE_LIMIT_REMINDER_TEST", "10/hour")

# When the app runs behind a trusted reverse proxy / load balancer (e.g.
# DigitalOcean App Platform), request.client.host is the PROXY's IP, not the
# real client's. Using it as the rate-limit key would bucket every user
# together under one IP, so the per-IP auth limits trip collectively. When
# TRUST_PROXY is on we key off the left-most X-Forwarded-For hop instead.
# SECURITY: only enable this when actually behind a proxy that sets
# X-Forwarded-For — otherwise clients can spoof the header to evade limits.
TRUST_PROXY = os.environ.get("TRUST_PROXY", "true").lower() in ("1", "true", "yes")

# ---- Account lockout settings ----
# After this many consecutive failed login attempts, the account is locked
# for LOCKOUT_DURATION_MINUTES. Both values are overridable via env.
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.environ.get("LOCKOUT_DURATION_MINUTES", "15"))

# ---- Password policy ----
PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", "12"))
PASSWORD_MAX_LENGTH = int(os.environ.get("PASSWORD_MAX_LENGTH", "64"))

# Commonly breached passwords — mirrors the frontend blocklist.
# Extend this set or replace with a full file-based blocklist as traffic grows.
COMMON_PASSWORDS = {
    "password", "123456", "12345678", "1234567890", "password1", "password123",
    "iloveyou", "admin", "welcome", "monkey", "dragon", "master", "letmein",
    "sunshine", "princess", "football", "shadow", "superman", "michael",
    "qwerty", "qwerty123", "abc123", "pass", "test", "hello", "welcome1",
    "passw0rd", "pa$$word", "p@ssword", "p@$$w0rd", "trustno1", "baseball",
}

# ---- Import upload limits ----
MAX_CSV_IMPORT_BYTES = int(os.environ.get("MAX_CSV_IMPORT_BYTES", 2 * 1024 * 1024))
MAX_CSV_IMPORT_ROWS = int(os.environ.get("MAX_CSV_IMPORT_ROWS", "500"))
MAX_SCREENSHOT_IMPORT_BYTES = int(
    os.environ.get("MAX_SCREENSHOT_IMPORT_BYTES", 8 * 1024 * 1024)
)
ALLOWED_SCREENSHOT_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_SCREENSHOT_PIXELS = 25_000_000

if _SLOWAPI_AVAILABLE:
    _storage_uri = os.environ.get("RATE_LIMIT_STORAGE_URI", "").strip() or None
    def _rate_limit_key(request: Request) -> str:
        if TRUST_PROXY:
            xff = request.headers.get("x-forwarded-for", "")
            if xff:
                # Left-most entry is the original client (set by the edge).
                return xff.split(",")[0].strip()
        return get_remote_address(request)

    limiter = Limiter(
        key_func=_rate_limit_key,
        enabled=RATE_LIMIT_ENABLED,
        storage_uri=_storage_uri,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def rate_limit(spec: str):
        return limiter.limit(spec)

else:  # pragma: no cover

    def rate_limit(spec: str):
        def _decorator(func):
            return func

        return _decorator

JWT_ALGO = "HS256"
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET environment variable is required for secure token signing"
    )


# ============== Password Validation ==============
def validate_password_policy(password: str, email: str = "", name: str = "") -> str:
    """
    Returns an error message string if the password violates policy,
    or an empty string if the password is acceptable.
    Mirrors the frontend getPasswordStrength logic so both layers agree.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Password must be no more than {PASSWORD_MAX_LENGTH} characters."

    lower = password.lower()

    if lower in COMMON_PASSWORDS:
        return "That password is too common and has appeared in known data breaches."

    email_local = email.split("@")[0].lower() if email else ""
    if email_local and len(email_local) > 2 and email_local in lower:
        return "Password cannot contain your email address."

    name_part = name.lower().replace(" ", "") if name else ""
    if name_part and len(name_part) > 2 and name_part in lower:
        return "Password cannot contain your name."

    if "illinoisjobtracker" in lower or "iltracker" in lower:
        return "Password cannot contain the site name."

    return ""


# ============== Models ==============
class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str = "user"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=64)
    name: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    dob: Optional[str] = None
    address: str = ""
    city: str = ""
    zip: str = ""
    claimant_id: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthOut(BaseModel):
    token: str
    user: UserPublic


class RegisterOut(BaseModel):
    message: str
    user: UserPublic


class ProfileIn(BaseModel):
    label: str = "Primary"
    first_name: str = ""
    last_name: str = ""
    middle_initial: str = ""
    claimant_id: str = ""
    address: str = ""
    city: str = ""
    state: str = "IL"
    zip_code: str = ""
    phone: str = ""
    occupation: str = ""
    reminders_enabled: bool = True
    reminder_email: str = ""
    sms_enabled: bool = False


class Profile(ProfileIn):
    id: str
    user_id: str
    updated_at: datetime
    sms_phone: str = ""
    sms_verified: bool = False


class ForgotPwIn(BaseModel):
    email: EmailStr


class ResetPwIn(BaseModel):
    token: str
    password: str = Field(min_length=12, max_length=64)


class InviteCreate(BaseModel):
    email: EmailStr
    claimant_label: str = "Primary"
    note: str = ""


class InviteRedeem(BaseModel):
    code: str
    password: str = Field(min_length=12, max_length=64)
    name: str


class BenefitWeekIn(BaseModel):
    week_start: str
    week_end: str
    notes: str = ""
    certified: bool = False
    # IDES compliance questions (None = not yet answered)
    able_to_work: Optional[bool] = None
    available_for_work: Optional[bool] = None
    worked_for_pay: Optional[bool] = None


class BenefitWeek(BenefitWeekIn):
    id: str
    user_id: str
    created_at: datetime


class ContactIn(BaseModel):
    benefit_week_id: str
    contact_date: str
    employer_name: str
    employer_address: str = ""
    contact_method: Literal[
        "In Person", "Phone", "Email", "Online", "Mail", "Other"
    ] = "Online"
    type_of_work: str = ""
    position_applied: str = ""
    person_contacted: str = ""
    result: str = ""
    source_url: str = ""


class Contact(ContactIn):
    id: str
    user_id: str
    created_at: datetime


class AuditEntry(BaseModel):
    id: str
    user_id: str
    action: str
    entity: str
    entity_id: Optional[str] = None
    detail: str = ""
    timestamp: datetime


# ============== Auth Utils ==============
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    try:
        if hasattr(jwt, "encode"):
            return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    except Exception:
        pass

    import base64
    import hashlib
    import hmac
    import json

    def _b64u(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = {"alg": JWT_ALGO, "typ": "JWT"}
    header_b64 = _b64u(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64u(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64u(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


async def get_current_user(request: Request) -> dict:
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = None
    try:
        if hasattr(jwt, "decode"):
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception as e:
        err = e

    if payload is None:
        try:
            import base64
            import hashlib
            import hmac
            import json

            def _b64ud(s: str) -> bytes:
                s2 = s + "=" * (-len(s) % 4)
                return base64.urlsafe_b64decode(s2.encode())

            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid token format")
            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode()
            expected_sig = hmac.new(
                JWT_SECRET.encode(), signing_input, hashlib.sha256
            ).digest()
            sig = _b64ud(sig_b64)
            if not hmac.compare_digest(sig, expected_sig):
                raise ValueError("Invalid signature")
            payload_json = _b64ud(payload_b64)
            payload = json.loads(payload_json)
        except ValueError as e:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    try:
        exp = int(payload.get("exp", 0))
        if datetime.now(timezone.utc).timestamp() > exp:
            raise HTTPException(status_code=401, detail="Token expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one(
        {"id": payload["sub"]}, {"_id": 0, "password_hash": 0}
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("deleted"):
        # Account is scheduled for deletion — access is revoked immediately even
        # though the data isn't purged until purge_after.
        raise HTTPException(status_code=401, detail="Account has been deleted")
    return user


async def log_audit(
    user_id: str, action: str, entity: str, entity_id: str = None, detail: str = ""
):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.audit_log.insert_one(doc)


def diff_dict(old: dict, new: dict, keys: list) -> str:
    parts = []
    for k in keys:
        ov = (old or {}).get(k, "")
        nv = (new or {}).get(k, "")
        if (ov or "") != (nv or ""):
            parts.append(f"{k}: '{ov}' → '{nv}'")
    return "; ".join(parts) if parts else "no changes"


async def get_active_claimant_id(user_id: str) -> Optional[str]:
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "active_claimant_id": 1})
    if u and u.get("active_claimant_id"):
        return u["active_claimant_id"]
    p = await db.profiles.find_one({"user_id": user_id}, {"_id": 0, "id": 1})
    return p["id"] if p else None


async def send_email(to_email: str, subject: str, html: str) -> bool:
    api_key = os.environ.get("MAILGUN_API_KEY", "")
    domain = os.environ.get("MAILGUN_DOMAIN", "")
    sender = os.environ.get("MAILGUN_FROM", "")
    if not api_key or not domain or not to_email:
        logging.warning("Mailgun not configured — skipping email")
        return False
    try:
        response = http_requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data={
                "from": sender,
                "to": to_email,
                "subject": subject,
                "html": html,
            },
        )
        if response.status_code == 200:
            logging.info(f"Mailgun sent to {to_email}")
            return True
        logging.warning(f"Mailgun failed: {response.status_code} {response.text}")
        return False
    except Exception as e:
        logging.warning(f"Mailgun error: {e}")
        return False


def send_sms(to_number: str, body: str) -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_num = os.environ.get("TWILIO_FROM_NUMBER", "")
    if not (sid and token and from_num and to_number):
        return False
    try:
        client = TwilioClient(sid, token)
        client.messages.create(from_=from_num, to=to_number, body=body[:1500])
        return True
    except Exception as e:
        logging.warning(f"Twilio SMS failed: {e}")
        return False


SMS_MIN_INTERVAL_MINUTES = int(os.environ.get("SMS_MIN_INTERVAL_MINUTES", "30"))


async def send_sms_rate_limited(
    phone: str, body: str, claimant_id: str = ""
) -> tuple[bool, str]:
    if not phone:
        return False, "no phone"
    last = await db.sms_log.find_one({"phone": phone}, sort=[("sent_at", -1)])
    if last:
        last_at = last.get("sent_at")
        if isinstance(last_at, str):
            last_at = datetime.fromisoformat(last_at)
        if last_at and last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last_at
        if delta.total_seconds() < SMS_MIN_INTERVAL_MINUTES * 60:
            return (
                False,
                f"rate-limited ({int(delta.total_seconds() / 60)}m / {SMS_MIN_INTERVAL_MINUTES}m)",
            )
    ok = send_sms(phone, body)
    if ok:
        await db.sms_log.insert_one(
            {
                "phone": phone,
                "claimant_id": claimant_id,
                "body_preview": body[:120],
                "sent_at": datetime.now(timezone.utc),
            }
        )
    return ok, "ok" if ok else "twilio-error"


def to_public_user(u: dict) -> UserPublic:
    return UserPublic(
        id=u["id"], email=u["email"], name=u.get("name", ""), role=u.get("role", "user")
    )


# ============== Account Lockout Helpers ==============
async def _check_account_lockout(email: str):
    """
    Raises HTTP 429 if the account is currently locked out.
    Call this BEFORE verifying the password on login.
    """
    rec = await db.login_attempts.find_one({"email": email})
    if not rec:
        return
    locked_until = rec.get("locked_until")
    if locked_until:
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < locked_until:
            remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Account temporarily locked due to too many failed login attempts. "
                       f"Try again in {remaining} minute(s).",
            )
        else:
            # Lockout expired — clear it
            await db.login_attempts.delete_one({"email": email})


async def _record_failed_login(email: str):
    """
    Increments the failed attempt counter. Locks the account if the
    threshold is reached.
    """
    now = datetime.now(timezone.utc)
    rec = await db.login_attempts.find_one({"email": email})
    attempts = (rec.get("attempts", 0) if rec else 0) + 1
    update: dict = {"attempts": attempts, "last_attempt": now.isoformat()}
    if attempts >= LOGIN_MAX_ATTEMPTS:
        locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        update["locked_until"] = locked_until.isoformat()
        logging.warning(
            f"Account locked: {email} after {attempts} failed attempts. "
            f"Locked until {locked_until.isoformat()}"
        )
    await db.login_attempts.update_one(
        {"email": email}, {"$set": update}, upsert=True
    )


async def _clear_failed_logins(email: str):
    """Clears the failed attempt record on successful login."""
    await db.login_attempts.delete_one({"email": email})


# ============== Claimant management endpoints removed ==============
# The multi-claimant feature was removed for regular users. Each user now has a
# single profile, managed via GET/PUT /profile above. The list/create/update/
# delete/set-active endpoints were intentionally deleted so extra profiles can't
# be created via the API. `get_active_claimant_id` is retained because every
# per-user query (weeks, contacts, reports) still scopes by the active profile.


# ============== Account Deletion (soft delete + scheduled purge) ==============
# Number of days a soft-deleted account is retained before its data is hard-
# purged from every collection. Access is revoked immediately on deletion.
ACCOUNT_PURGE_GRACE_DAYS = int(os.environ.get("ACCOUNT_PURGE_GRACE_DAYS", "30"))

# Collections that store a row per user, keyed by `user_id`.
_USER_SCOPED_COLLECTIONS = [
    "profiles", "benefit_weeks", "contacts", "calendar_events",
    "document_files", "audit_log", "password_resets", "subscriptions",
    "usage_counters", "otp_codes",
]
# Collections keyed by the profile/claimant id.
_PROFILE_SCOPED_COLLECTIONS = ["sms_log"]
# Collections keyed by the account email.
_EMAIL_SCOPED_COLLECTIONS = ["login_attempts", "email_events", "invites"]


class DeleteAccountIn(BaseModel):
    email: str
    confirm_name: str
    confirm: bool = False


async def _purge_user_everywhere(uid: str, email: str) -> dict:
    """
    Hard-delete every trace of a user across all collections. Used by the
    scheduled purge job (and could be called directly for an immediate purge).
    Returns a per-collection deleted-count map for logging.
    """
    # Gather the user's profile ids so we can clean profile-scoped collections.
    pids = [
        p["id"]
        async for p in db.profiles.find({"user_id": uid}, {"_id": 0, "id": 1})
    ]
    counts = {}
    for coll in _USER_SCOPED_COLLECTIONS:
        res = await db[coll].delete_many({"user_id": uid})
        counts[coll] = res.deleted_count
    if pids:
        for coll in _PROFILE_SCOPED_COLLECTIONS:
            res = await db[coll].delete_many({"claimant_id": {"$in": pids}})
            counts[coll] = res.deleted_count
    if email:
        for coll in _EMAIL_SCOPED_COLLECTIONS:
            res = await db[coll].delete_many({"email": email})
            counts[coll] = counts.get(coll, 0) + res.deleted_count
    res = await db.users.delete_one({"id": uid})
    counts["users"] = res.deleted_count
    return counts


async def _purge_due_accounts() -> None:
    """Scheduled: hard-purge accounts whose grace window has elapsed."""
    now = datetime.now(timezone.utc)
    async for u in db.users.find(
        {"deleted": True}, {"_id": 0, "id": 1, "email": 1, "purge_after": 1}
    ):
        purge_after = u.get("purge_after")
        if isinstance(purge_after, str):
            purge_after = datetime.fromisoformat(purge_after)
        if purge_after and purge_after.tzinfo is None:
            purge_after = purge_after.replace(tzinfo=timezone.utc)
        if not purge_after or now >= purge_after:
            counts = await _purge_user_everywhere(u["id"], u.get("email", ""))
            logging.info(f"Purged deleted account {u.get('email')}: {counts}")


# ============== Calendar Events ==============
class CalendarEventIn(BaseModel):
    event_date: str  # ISO YYYY-MM-DD
    event_type: Literal[
        "certification", "ides_interview", "appeal", "questionnaire", "other"
    ]
    title: str
    notes: str = ""
    claimant_id: Optional[str] = None


# ============== Document Upload (IDES Paperwork) ==============
DOC_TYPES = Literal[
    "determination_letter",
    "certification_form",
    "questionnaire",
    "appeal_notice",
    "overpayment_notice",
    "correspondence",
    "other",
]
MAX_DOC_BYTES = int(os.environ.get("MAX_DOC_UPLOAD_BYTES", str(4 * 1024 * 1024)))  # 4 MB
DOC_MIME_ALLOWLIST = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


# ============== Admin (case-worker) ==============
async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ============== Reminders ==============
def _reminder_html(title: str, body_html: str) -> str:
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="color-scheme" content="light dark">
      <meta name="supported-color-schemes" content="light dark">
      <style>
        @media (prefers-color-scheme: dark) {{
          .email-bg    {{ background-color: #1a1a1a !important; }}
          .email-body  {{ background-color: #2a2a2a !important; border-color: #444 !important; }}
          .email-text  {{ color: #e4e4e7 !important; }}
          .email-muted {{ color: #a1a1aa !important; }}
          .login-btn   {{ background-color: #3b5fc0 !important; }}
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
          <h2 style="margin:0 0 16px; font-family:'Chivo',Arial,sans-serif; font-weight:900; color:#09090B; letter-spacing:-0.01em;" class="email-text">{title}</h2>
          <div style="color:#09090B;" class="email-text">{body_html}</div>
          <div style="margin:28px 0 20px;">
            <a href="{frontend_url}" class="login-btn"
               style="display:inline-block; background:#0033A0; color:#ffffff; padding:12px 24px; text-decoration:none; font-weight:600; font-size:14px; border-radius:2px;">
              Log In to Illinois UI Tracker
            </a>
          </div>
          <hr style="border:none; border-top:1px solid #e4e4e7; margin:20px 0;">
          <p style="font-size:12px; color:#52525B; margin:0;" class="email-muted">
            Illinois law requires a minimum of <strong>3 work-search contacts</strong> per benefit week (Sunday–Saturday).<br>
            You can disable reminders from your Claimant profile inside the app.
          </p>
        </div>
      </div>
    </body>
    </html>
    """


def _current_week_bounds(tz_str: str = "America/Chicago"):
    tz = pytz.timezone(tz_str)
    now = datetime.now(tz)
    days_since_sun = (now.weekday() + 1) % 7
    sunday = (now - timedelta(days=days_since_sun)).date()
    saturday = sunday + timedelta(days=6)
    return sunday.isoformat(), saturday.isoformat()


async def _send_user_reminder(user: dict, kind: str):
    if not user.get("email_verified", False):
        return 0
    claimants = await db.profiles.find(
        {"user_id": user["id"], "reminders_enabled": {"$ne": False}}, {"_id": 0}
    ).to_list(50)
    if not claimants:
        return 0
    sun, sat = _current_week_bounds()
    sent = 0
    for c in claimants:
        w = await db.benefit_weeks.find_one(
            {"user_id": user["id"], "claimant_id": c["id"], "week_start": sun, "week_end": sat},
            {"_id": 0},
        )
        contacts_count = 0
        contacts_list = []
        if w:
            contacts_list = await db.contacts.find({"benefit_week_id": w["id"]}, {"_id": 0}).to_list(50)
            contacts_count = len(contacts_list)

        to_email = c.get("reminder_email") or user.get("email")
        name = html.escape(
            f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            or c.get("label", "claimant")
        )
        deficit = max(0, 3 - contacts_count)

        def _contact_line(x, with_position=False):
            date_ = html.escape(str(x.get("contact_date", "")))
            employer = html.escape(str(x.get("employer_name", "")))
            if with_position:
                position = html.escape(str(x.get("position_applied", "") or x.get("type_of_work", "")))
                return f"<li>{date_} — {employer} ({position})</li>"
            return f"<li>{date_} — {employer}</li>"

        if kind == "sunday":
            title = "New Benefit Week Starting"
            body = f"<p>Hi {name}, your new benefit week ({sun} → {sat}) starts today. Aim for at least 3 work-search contacts this week.</p>"
        elif kind == "wednesday":
            if contacts_count >= 3:
                continue
            title = f"Mid-Week Check — {deficit} contact{'s' if deficit != 1 else ''} to go"
            body = f"<p>Hi {name}, you're at <b>{contacts_count} / 3</b> contacts for the week {sun} → {sat}. Keep going!</p>"
        elif kind == "friday":
            title = f"Friday Reminder — {contacts_count} / 3 contacts logged"
            list_html = "".join(_contact_line(x, with_position=True) for x in contacts_list)
            body = (
                f"<p>Hi {name}, you have <b>{contacts_count} / 3</b> contacts for {sun} → {sat}.</p>"
                + (f"<ul>{list_html}</ul>" if list_html else "")
            )
            if contacts_count < 3:
                body += f"<p style='color:#DC2626; font-weight:600;'>Log {deficit} more before Saturday end-of-day to stay compliant.</p>"
        elif kind == "saturday":
            title = "End-of-Week Summary"
            status_txt = "✅ Compliant" if contacts_count >= 3 else "⚠️ Non-compliant"
            list_html = "".join(_contact_line(x) for x in contacts_list)
            body = (
                f"<p>Hi {name}, here's your summary for {sun} → {sat}:</p><p><b>{contacts_count} contacts logged</b> — {status_txt}</p>"
                + (f"<ul>{list_html}</ul>" if list_html else "")
            )
        else:
            return 0

        html_body = _reminder_html(title, body)
        ok = await send_email(to_email, title, html_body)
        if ok:
            sent += 1
            await log_audit(user["id"], f"REMINDER_{kind.upper()}", "claimant", c["id"], f"Email sent to {to_email}")

        if c.get("sms_enabled") and c.get("sms_phone") and c.get("sms_verified"):
            sms_text = f"[IL UI Tracker] {title}: {contacts_count}/3 contacts for week {sun}–{sat}."
            if kind == "friday" and contacts_count < 3:
                sms_text += f" Log {deficit} more by Sat."
            ok_sms, reason = await send_sms_rate_limited(c["sms_phone"], sms_text, c["id"])
            if ok_sms:
                await log_audit(user["id"], f"SMS_{kind.upper()}", "claimant", c["id"], f"SMS sent to {c['sms_phone']}")
            elif reason.startswith("rate-limited"):
                await log_audit(user["id"], "SMS_SKIPPED", "claimant", c["id"], f"{kind}: {reason}")
    return sent


async def _broadcast_reminders(kind: str):
    cursor = db.users.find({}, {"_id": 0})
    async for u in cursor:
        try:
            await _send_user_reminder(u, kind)
        except Exception as e:
            logging.warning(f"Reminder {kind} failed for {u.get('email')}: {e}")


# ============== SMS Phone OTP Verification ==============
class OtpSendIn(BaseModel):
    claimant_id: str
    phone: str


class OtpVerifyIn(BaseModel):
    claimant_id: str
    code: str


# ============== Mailgun Webhook ==============
async def _parse_mailgun_webhook(request: Request) -> dict:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        return await request.json()
    form = await request.form()
    payload = {k: v for k, v in form.items()}
    if "event-data" in payload:
        try:
            payload["data"] = json.loads(payload["event-data"])
        except Exception:
            payload["data"] = payload["event-data"]
    if "signature" in payload and isinstance(payload["signature"], str):
        try:
            payload["signature"] = json.loads(payload["signature"])
        except Exception:
            pass
    return payload


def _verify_mailgun_signature(payload: dict):
    signature_payload = payload.get("signature", {})
    if isinstance(signature_payload, str):
        try:
            signature_payload = json.loads(signature_payload)
        except Exception:
            signature_payload = {}

    timestamp = None
    token = None
    signature = None
    if isinstance(signature_payload, dict):
        timestamp = signature_payload.get("timestamp")
        token = signature_payload.get("token")
        signature = signature_payload.get("signature")

    timestamp = timestamp or payload.get("timestamp") or payload.get("signature[timestamp]")
    token = token or payload.get("token") or payload.get("signature[token]")
    signature = signature or payload.get("signature") or payload.get("signature[signature]")

    if not timestamp or not token or not signature:
        raise HTTPException(status_code=400, detail="Mailgun webhook signature missing")

    secret = os.environ.get("MAILGUN_API_KEY", "")
    if not secret:
        logging.warning("Mailgun webhook signature verification is not configured")
        raise HTTPException(status_code=503, detail="Mailgun webhook verification is not configured")

    expected = hmac.new(
        secret.encode("utf-8"), f"{timestamp}{token}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, str(signature)):
        raise HTTPException(status_code=403, detail="Invalid Mailgun webhook signature")


# ============== Bulk Invite (Admin) ==============
class BulkInviteIn(BaseModel):
    csv_text: str = ""
    note: str = ""


# ============== Contact Form (public — from marketing site) ==============
CONTACT_ALLOWED_ORIGINS = [
    "https://illinoisjobtracker.com",
    "https://www.illinoisjobtracker.com",
    "https://illinoisjobtracker.app",
    "https://www.illinoisjobtracker.app",
]

def _contact_cors_headers(request: Request) -> dict:
    origin = request.headers.get("origin", "")
    if origin in CONTACT_ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        }
    return {}

class ContactRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    reason: str
    message: str


REASON_CODES = {
    "Billing": "BIL",
    "Account": "ACC",
    "General Questions": "GEN",
    "Feedback": "FBK",
    "Request a Feature": "FTR",
    "Other": "OTH",
}

def _generate_ref(reason: str) -> str:
    import random
    code = REASON_CODES.get(reason, "OTH")
    number = random.randint(100000, 999999)
    return f"IJT-{code}-{number}"


# ============== CORS (must be registered before other middleware so it
# wraps outermost — this ensures CORS headers are attached even on error
# responses, e.g. HTTPException from /auth/verify-email) ==============
origins_env = os.environ.get("CORS_ORIGINS", "*")
allow_credentials = True
if origins_env.strip() == "*":
    allow_origins = ["*"]
    allow_credentials = False
else:
    allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
