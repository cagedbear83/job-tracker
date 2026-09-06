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

import jwt

import clerk_auth
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
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from starlette.middleware.cors import CORSMiddleware

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

# JWT signing config removed — Clerk mints and signs session tokens now,
# and clerk_auth.py verifies them against Clerk's public JWKS. JWT_SECRET
# is no longer read or required at boot.

ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "10"))
# Sliding idle expiry: each successful refresh pushes the refresh token's
# expiry forward by this many minutes from "now".
REFRESH_TOKEN_IDLE_MINUTES = int(os.environ.get("REFRESH_TOKEN_IDLE_MINUTES", "30"))
# Hard ceiling on a session, measured from the *original* login, regardless
# of activity — caps how long a stolen-but-still-being-refreshed token chain
# can be ridden.
REFRESH_TOKEN_ABSOLUTE_HOURS = int(os.environ.get("REFRESH_TOKEN_ABSOLUTE_HOURS", "12"))

# The refresh-token family/rotation table and its httpOnly cookie are gone.
# Clerk issues short-lived session tokens that the client refreshes itself,
# so there is no long-lived server-side session to rotate or revoke here.


# Password policy removed — Clerk enforces password rules (and breach
# detection) at sign-up and reset. Configure them in the Clerk dashboard
# under User & Authentication -> Email, Phone, Username.


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str = "user"
    # Was missing, so App.jsx's platformRoleFor() never saw it and always fell
    # through to the legacy `role == "admin"` branch.
    platform_role: str = "user"
    # True until the claimant profile exists — the app routes to /onboarding.
    needs_onboarding: bool = False


class OnboardingIn(BaseModel):
    """Claimant details collected right after Clerk sign-up.

    Registration used to collect these in the same POST that created the
    account. Clerk sign-up only yields an email and a password, so profile
    capture moved to its own step — same fields, same validation, minus the
    credentials Clerk now owns.
    """

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    sms_opt_in: bool = False
    dob: str = Field(min_length=1)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    zip: str = Field(min_length=1)
    claimant_id: Optional[str] = None
    knows_next_cert_date: Literal["yes", "no", "na"] = "na"
    next_certification_date: Optional[str] = None  # ISO YYYY-MM-DD

    @field_validator("first_name", "last_name", "phone", "dob", "address", "city", "zip")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=64)
    name: str
    # These were previously all-optional (defaulted to ""/None), which let
    # incomplete registrations through even though the Register page's own
    # punch-list item calls for marking them required. Enforced here too —
    # not just on the frontend — since the frontend check alone doesn't stop
    # someone hitting the API directly. min_length=1 rejects blank/whitespace
    # the same way FastAPI already rejects a missing field.
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    sms_opt_in: bool = False
    dob: str = Field(min_length=1)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    zip: str = Field(min_length=1)
    claimant_id: Optional[str] = None
    # "Do you know your next certification date?" — Yes/No/N/A. When "yes",
    # next_certification_date silently seeds 26 bi-weekly certification
    # calendar_events (see _seed_certification_events) so the claimant's
    # Calendar and certification reminders are populated ~1 year out without
    # them adding each one by hand.
    knows_next_cert_date: Literal["yes", "no", "na"] = "na"
    next_certification_date: Optional[str] = None  # ISO YYYY-MM-DD

    @field_validator("first_name", "last_name", "phone", "dob", "address", "city", "zip")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def _cert_date_required_if_known(self):
        if self.knows_next_cert_date == "yes":
            if not self.next_certification_date or not self.next_certification_date.strip():
                raise ValueError(
                    "next_certification_date is required when knows_next_cert_date is 'yes'"
                )
            try:
                datetime.strptime(self.next_certification_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError("next_certification_date must be an ISO date (YYYY-MM-DD)")
        return self


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
    # Consent evidence: when the user opted in to SMS (registration or later).
    # Not part of ProfileIn — not directly editable via PUT /profile.
    sms_opt_in_at: Optional[str] = None


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
# hash_password / verify_password / create_token removed — no credential
# ever reaches this server now.


async def get_current_user(request: Request) -> dict:
    """Resolve the caller from their Clerk session token.

    THE SEAM. Every router depends on this one function, so swapping its
    innards migrated the whole API to Clerk at once. It still returns the
    same Mongo user document every router already expects — `id`, `email`,
    `name`, `role`, `platform_role` — so nothing downstream changed.

    See clerk_auth.py for the division of responsibility: Clerk owns
    identity, this database owns authorization.
    """
    token = clerk_auth.extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    claims = clerk_auth.verify_session_token(token)
    user = await clerk_auth.get_or_create_user(db, claims)

    if user.get("deleted"):
        # Account is scheduled for deletion — access is revoked immediately
        # even though the data isn't purged until purge_after.
        raise HTTPException(status_code=401, detail="Account has been deleted")

    # Stash the verified claims so authorization helpers can read session
    # facts (notably `fva`, the factor verification age that backs step-up)
    # without every router signature having to grow a second parameter.
    # Underscore-prefixed: this is request-scoped, never persisted.
    user["_session_claims"] = claims
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
    username = os.environ.get("CLICKSEND_USERNAME", "")
    api_key = os.environ.get("CLICKSEND_API_KEY", "")
    from_num = os.environ.get("CLICKSEND_FROM_NUMBER", "")
    if not (username and api_key and to_number):
        return False
    try:
        message = {"source": "job-tracker", "to": to_number, "body": body[:1500]}
        if from_num:
            message["from"] = from_num
        response = http_requests.post(
            "https://rest.clicksend.com/v3/sms/send",
            auth=(username, api_key),
            json={"messages": [message]},
            timeout=15,
        )
        if response.status_code == 200:
            status = (response.json().get("data", {}).get("messages") or [{}])[0].get("status", "")
            if status == "SUCCESS":
                return True
            logging.warning(f"ClickSend SMS not accepted: {status} — {response.text}")
            return False
        logging.warning(f"ClickSend failed: {response.status_code} {response.text}")
        return False
    except Exception as e:
        logging.warning(f"ClickSend SMS error: {e}")
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
    ok = await asyncio.to_thread(send_sms, phone, body)
    if ok:
        await db.sms_log.insert_one(
            {
                "phone": phone,
                "claimant_id": claimant_id,
                "body_preview": body[:120],
                "sent_at": datetime.now(timezone.utc),
            }
        )
    return ok, "ok" if ok else "clicksend-error"


def to_public_user(u: dict) -> UserPublic:
    return UserPublic(
        id=u["id"], email=u["email"], name=u.get("name", ""), role=u.get("role", "user")
    )


# ============== Account Lockout Helpers ==============
# Login-attempt lockout removed — Clerk rate-limits and locks sign-in
# attempts upstream, and no sign-in request reaches this server to count.


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


async def _seed_certification_events(user_id: str, claimant_id: str, first_date: str, occurrences: int = 26) -> int:
    """
    Auto-seeds `occurrences` bi-weekly certification calendar_events (14-day
    cadence, starting at `first_date`) — used at registration when a claimant
    tells us their next certification date (Register page: "Do you know your
    next certification date?"). IDES certifications run every 2 weeks, so
    this keeps ~1 year of certification dates on the Calendar without the
    claimant adding each one by hand. Written directly to the collection
    (bypasses the calendar_events tier gate that applies to the manual
    create/update endpoints) — a certification deadline is a compliance date,
    not the same thing as the paid "manage your own calendar" feature, so
    every new account gets these regardless of tier.
    """
    try:
        start = datetime.strptime(first_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0
    now = datetime.now(timezone.utc)
    docs = [
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "event_date": (start + timedelta(weeks=2 * i)).isoformat(),
            "event_type": "certification",
            "title": "Certification Due",
            "notes": "Auto-added at registration from your certification schedule.",
            "claimant_id": claimant_id,
            "created_at": now,
        }
        for i in range(occurrences)
    ]
    if docs:
        await db.calendar_events.insert_many(docs)
    return len(docs)


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
            sms_text += " Reply STOP to opt out, HELP for help."
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


# ============== Calendar Event Reminders ==============
# Generic reminder engine for calendar_events (certification, IDES interview,
# appeal, questionnaire, and the auto-added work-search follow-up, which
# rides on event_type "other" — see contacts.py's create_contact). Built to
# scan calendar_events itself rather than any one event's origin, so it
# automatically covers both hand-added events and system-seeded ones (Register
# page's 26-week certification auto-seed, contacts.py's 5-business-day
# follow-up) with no special-casing needed for either.
#
# Reminders fire regardless of subscription tier, matching the Aug 20 call on
# Register's certification-date seeding: a compliance deadline (or a
# system-generated follow-up) isn't the same thing as the paid "manage your
# own calendar" feature that gate_feature enforces on manual create/update.

EVENT_TYPE_LABELS = {
    "certification": "Certification",
    "ides_interview": "IDES Interview",
    "appeal": "Appeal Deadline",
    "questionnaire": "Questionnaire Due",
    "other": "Reminder",
}


def _add_business_days(start: date, n: int) -> date:
    """Adds `n` business days (Mon-Fri) to `start`, skipping weekends."""
    d = start
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


async def _due_calendar_events(days_ahead: int, event_type: str = None, exclude_type: str = None):
    """
    Returns every calendar_events doc whose event_date lands `days_ahead`
    calendar days from today, in America/Chicago (the app's one timezone —
    IDES deadlines run on Illinois time regardless of where a claimant is
    physically logging in from).
    """
    tz = pytz.timezone("America/Chicago")
    target_date = (datetime.now(tz) + timedelta(days=days_ahead)).date().isoformat()
    query = {"event_date": target_date}
    if event_type:
        query["event_type"] = event_type
    if exclude_type:
        query["event_type"] = {"$ne": exclude_type}
    return await db.calendar_events.find(query, {"_id": 0}).to_list(1000)


async def _broadcast_event_reminders(kind: str):
    """
    Daily scan, fired at 8AM CT for both `kind`s (see server.py). "3day"
    reminds 3 calendar days ahead of event_date; "morning" reminds the day
    of. Certification events are excluded from "morning" — they get their
    own dedicated 5PM CT email+SMS reminder instead (see
    _send_certification_final_reminders), since the punch list specifically
    wants the LAST certification reminder to land close to the 7PM CT filing
    cutoff, not first thing in the morning.
    """
    days_ahead = 3 if kind == "3day" else 0
    exclude = "certification" if kind == "morning" else None
    events = await _due_calendar_events(days_ahead, exclude_type=exclude)
    sent = 0
    for ev in events:
        try:
            user = await db.users.find_one({"id": ev["user_id"]}, {"_id": 0})
            if not user or not user.get("email_verified", False):
                continue
            claimant = None
            if ev.get("claimant_id"):
                claimant = await db.profiles.find_one({"id": ev["claimant_id"]}, {"_id": 0})
            to_email = (claimant.get("reminder_email") if claimant else "") or user.get("email")
            label = EVENT_TYPE_LABELS.get(ev["event_type"], ev["event_type"].replace("_", " ").title())
            when = "in 3 days" if kind == "3day" else "today"
            title = f"{label} {when} — {ev['event_date']}"
            body = f"<p>Reminder: <b>{html.escape(ev.get('title') or label)}</b> is scheduled for {ev['event_date']} ({when}).</p>"
            if ev.get("notes"):
                body += f"<p>{html.escape(ev['notes'])}</p>"
            ok = await send_email(to_email, title, _reminder_html(title, body))
            if ok:
                sent += 1
                await log_audit(
                    user["id"], f"CALENDAR_REMINDER_{kind.upper()}", "calendar_event",
                    ev["id"], f"Email sent to {to_email}",
                )
        except Exception as e:
            logging.warning(f"Calendar reminder ({kind}) failed for event {ev.get('id')}: {e}")
    return sent


async def _send_certification_final_reminders():
    """
    Fires at 5PM CT (see server.py) — the LAST reminder before the 7PM CT
    IDES filing cutoff, for any certification calendar_event landing today.
    Sent over email AND SMS, since a missed certification is a bigger deal
    than a missed work-search contact (matches the Aug 20 decision to send
    this one over both channels where the weekly work-search reminders are
    email-first with SMS as a bonus).
    """
    events = await _due_calendar_events(0, event_type="certification")
    sent = 0
    for ev in events:
        try:
            user = await db.users.find_one({"id": ev["user_id"]}, {"_id": 0})
            if not user or not user.get("email_verified", False):
                continue
            claimant = None
            if ev.get("claimant_id"):
                claimant = await db.profiles.find_one({"id": ev["claimant_id"]}, {"_id": 0})
            to_email = (claimant.get("reminder_email") if claimant else "") or user.get("email")
            title = "Certification due today — file by 7PM CT"
            body = (
                f"<p style='color:#DC2626; font-weight:600;'>Your certification is due "
                f"today ({ev['event_date']}). IDES's filing window closes at "
                f"<b>7PM CT</b> — file with time to spare.</p>"
            )
            ok = await send_email(to_email, title, _reminder_html(title, body))
            if ok:
                sent += 1
                await log_audit(
                    user["id"], "CALENDAR_REMINDER_CERT_FINAL", "calendar_event",
                    ev["id"], f"Email sent to {to_email}",
                )
            if claimant and claimant.get("sms_enabled") and claimant.get("sms_phone") and claimant.get("sms_verified"):
                sms_text = "[IL UI Tracker] Certification due today — file by 7PM CT. Reply STOP to opt out, HELP for help."
                ok_sms, reason = await send_sms_rate_limited(claimant["sms_phone"], sms_text, claimant["id"])
                if ok_sms:
                    await log_audit(
                        user["id"], "SMS_CALENDAR_CERT_FINAL", "claimant",
                        claimant["id"], f"SMS sent to {claimant['sms_phone']}",
                    )
        except Exception as e:
            logging.warning(f"Certification final reminder failed for event {ev.get('id')}: {e}")
    return sent


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