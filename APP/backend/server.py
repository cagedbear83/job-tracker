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
from fastapi.responses import JSONResponse, Response, StreamingResponse
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
# No-op unless SENTRY_DSN is set, so local/dev runs are unaffected.
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
    except Exception as e:  # pragma: no cover - never let monitoring break boot
        logging.warning(f"Sentry init failed: {e}")

# ---- DB ----
# Single-worker, long-running OLTP API (short CRUD queries) connecting to a
# MongoDB Atlas replica set. The client is created once at import and reused
# (correct for a long-running process — not a serverless handler). Values are
# conservative for small Atlas tiers / a low-traffic launch and are all
# overridable via env so production can be tuned without code changes.
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(
    mongo_url,
    appname=os.environ.get("MONGO_APP_NAME", "ides-job-tracker"),
    # One worker + low concurrency: a small ceiling is plenty and keeps the
    # connection footprint tiny on shared/free Atlas tiers. Raise as traffic grows.
    maxPoolSize=int(os.environ.get("MONGO_MAX_POOL_SIZE", "20")),
    # No pre-warmed idle connections by default (each costs ~1 MB on the server).
    minPoolSize=int(os.environ.get("MONGO_MIN_POOL_SIZE", "0")),
    # Fail fast on topology/connection problems so /health/ready returns 503
    # promptly instead of hanging on the ~30s default.
    serverSelectionTimeoutMS=int(
        os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")
    ),
    connectTimeoutMS=int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "10000")),
)
db = client[os.environ["DB_NAME"]]

# ---- App ----
app = FastAPI(title="Illinois UI Job Search Tracker")
api = APIRouter(prefix="/api")

# ---- Rate limiting ----
# Per-IP limits on abuse-prone auth endpoints. In-memory by default; set
# RATE_LIMIT_STORAGE_URI (e.g. a Redis URL) for a shared store across workers.
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
RATE_LIMIT_LOGIN = os.environ.get("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_REGISTER = os.environ.get("RATE_LIMIT_REGISTER", "3/hour")
RATE_LIMIT_FORGOT = os.environ.get("RATE_LIMIT_FORGOT", "3/hour")
RATE_LIMIT_REMINDER_TEST = os.environ.get("RATE_LIMIT_REMINDER_TEST", "10/hour")

# ---- Import upload limits ----
# Unbounded uploads let any authenticated user exhaust memory/DB storage
# (CSV) or rack up Gemini API cost (screenshot OCR). Keep generous but finite
# caps; override via env if a deployment legitimately needs more headroom.
MAX_CSV_IMPORT_BYTES = int(os.environ.get("MAX_CSV_IMPORT_BYTES", 2 * 1024 * 1024))
MAX_CSV_IMPORT_ROWS = int(os.environ.get("MAX_CSV_IMPORT_ROWS", "500"))
MAX_SCREENSHOT_IMPORT_BYTES = int(
    os.environ.get("MAX_SCREENSHOT_IMPORT_BYTES", 8 * 1024 * 1024)
)
ALLOWED_SCREENSHOT_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_SCREENSHOT_PIXELS = 25_000_000  # ~5000x5000; blocks decompression-bomb-style images
if _SLOWAPI_AVAILABLE:
    _storage_uri = os.environ.get("RATE_LIMIT_STORAGE_URI", "").strip() or None
    limiter = Limiter(
        key_func=get_remote_address,
        enabled=RATE_LIMIT_ENABLED,
        storage_uri=_storage_uri,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def rate_limit(spec: str):
        return limiter.limit(spec)

else:  # pragma: no cover - slowapi missing; limits become no-ops

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


# ============== Models ==============
class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str = "user"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    dob: Optional[str] = None  # ISO date YYYY-MM-DD
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
    # sms_phone/sms_verified are set only by the /sms/verify-otp flow, never
    # accepted as direct input — otherwise a client could mark any phone
    # number "verified" and trigger SMS sends to it without proving it
    # belongs to them. See sms_send_otp / sms_verify_otp.
    sms_phone: str = ""  # E.164 format e.g. +13125550100
    sms_verified: bool = False


class ForgotPwIn(BaseModel):
    email: EmailStr


class ResetPwIn(BaseModel):
    token: str
    password: str = Field(min_length=6)


class InviteCreate(BaseModel):
    email: EmailStr
    claimant_label: str = "Primary"
    note: str = ""


class InviteRedeem(BaseModel):
    code: str
    password: str = Field(min_length=6)
    name: str


class BenefitWeekIn(BaseModel):
    week_start: str  # ISO date YYYY-MM-DD (Sunday)
    week_end: str  # ISO date (Saturday)
    notes: str = ""
    certified: bool = False


class BenefitWeek(BenefitWeekIn):
    id: str
    user_id: str
    created_at: datetime


class ContactIn(BaseModel):
    benefit_week_id: str
    contact_date: str  # ISO date
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
    # Use numeric timestamps for JWT claims
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    # Prefer PyJWT if available, otherwise use a small HMAC-SHA256 implementation
    try:
        if hasattr(jwt, "encode"):
            return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    except Exception:
        pass

    # Fallback: construct JWT by hand (HS256)
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
    # Try PyJWT decode first, otherwise use fallback HMAC validation
    payload = None
    try:
        if hasattr(jwt, "decode"):
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception as e:
        # PyJWT raised an error; map to HTTP errors below
        err = e

    if payload is None:
        # Fallback decode: validate HMAC and parse payload
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

    # Verify exp
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


# SMS rate limit: minimum minutes between SMS to same phone
SMS_MIN_INTERVAL_MINUTES = int(os.environ.get("SMS_MIN_INTERVAL_MINUTES", "30"))


async def send_sms_rate_limited(
    phone: str, body: str, claimant_id: str = ""
) -> tuple[bool, str]:
    """Returns (sent, reason). Enforces per-phone rate limit via Mongo."""
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


# ============== Auth Endpoints ==============
@api.post("/auth/register", response_model=RegisterOut)
@rate_limit(RATE_LIMIT_REGISTER)
async def register(request: Request, body: RegisterIn):
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

    # After creating user, auto-create their claimant profile
    await db.profiles.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "full_name": f"{body.first_name} {body.last_name}".strip(),
            "phone": body.phone,
            "date_of_birth": body.dob,
            "address": body.address,
            "city": body.city,
            "zip": body.zip,
            "claimant_id": body.claimant_id or "",
            "is_primary": True,
            "created_at": datetime.now(timezone.utc),
        }
    )

    # After creating user, send verification email
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
    verify_url = (
        f"{os.environ.get('FRONTEND_URL')}/verify-email?token={verification_token}"
    )
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
    # No session token is issued here: the account is unverified, and the
    # only way to obtain a token is /auth/login, which rejects unverified
    # accounts. This prevents an attacker from registering a victim's email
    # and using an authenticated session before the victim ever sees the
    # verification email (account pre-hijacking).
    return RegisterOut(
        message="Account created. Please check your email to verify your address before logging in.",
        user=UserPublic(id=uid, email=email, name=body.name, role="user"),
    )


@api.post("/auth/login", response_model=AuthOut)
@rate_limit(RATE_LIMIT_LOGIN)
async def login(request: Request, body: LoginIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("email_verified", False):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email address before logging in.",
        )
    token = create_token(user["id"], user["email"])
    await log_audit(user["id"], "LOGIN", "user", user["id"], f"Login successful")
    return AuthOut(
        token=token,
        user=UserPublic(
            id=user["id"],
            email=user["email"],
            name=user.get("name", ""),
            role=user.get("role", "user"),
        ),
    )


@api.get("/auth/verify-email")
async def verify_email(token: str):
    user = await db.users.find_one({"verification_token": token})
    if not user:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification token"
        )
    expires = user.get("verification_token_expires")
    if expires and datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Verification link has expired")
    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {"email_verified": True},
            "$unset": {"verification_token": "", "verification_token_expires": ""},
        },
    )
    return {"message": "Email verified successfully"}


@api.post("/auth/logout")
async def logout(user=Depends(get_current_user)):
    await log_audit(user["id"], "LOGOUT", "user", user["id"], "Logout")
    return {"ok": True}


@api.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return UserPublic(
        id=user["id"],
        email=user["email"],
        name=user.get("name", ""),
        role=user.get("role", "user"),
    )


# ============== Claimant Profiles (multi) ==============
@api.get("/profile")
async def get_active_profile(user=Depends(get_current_user)):
    """Backward-compat: returns the active claimant profile."""
    cid = await get_active_claimant_id(user["id"])
    if not cid:
        return None
    return await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})


@api.put("/profile")
async def upsert_profile(body: ProfileIn, user=Depends(get_current_user)):
    """Backward-compat: upserts the active claimant profile."""
    cid = await get_active_claimant_id(user["id"])
    now = datetime.now(timezone.utc).isoformat()
    if cid:
        existing = (
            await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
            or {}
        )
        update = body.model_dump()
        update["updated_at"] = now
        await db.profiles.update_one(
            {"id": cid, "user_id": user["id"]}, {"$set": update}
        )
        diff = diff_dict(existing, update, list(body.model_dump().keys()))
        await log_audit(
            user["id"], "UPDATE", "claimant", cid, f"Claimant updated — {diff}"
        )
        return {**existing, **update}
    pid = str(uuid.uuid4())
    doc = {"id": pid, "user_id": user["id"], "updated_at": now, **body.model_dump()}
    await db.profiles.insert_one(doc)
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_claimant_id": pid}})
    await log_audit(
        user["id"], "CREATE", "claimant", pid, f"Claimant created: {body.label}"
    )
    doc.pop("_id", None)
    return doc


@api.get("/claimants")
async def list_claimants(user=Depends(get_current_user)):
    items = (
        await db.profiles.find({"user_id": user["id"]}, {"_id": 0})
        .sort("label", 1)
        .to_list(100)
    )
    active = await get_active_claimant_id(user["id"])
    return {"items": items, "active_id": active}


@api.post("/claimants")
async def create_claimant(body: ProfileIn, user=Depends(get_current_user)):
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {"id": pid, "user_id": user["id"], "updated_at": now, **body.model_dump()}
    await db.profiles.insert_one(doc)
    # If user has no active, make this active
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "active_claimant_id": 1})
    if not u or not u.get("active_claimant_id"):
        await db.users.update_one(
            {"id": user["id"]}, {"$set": {"active_claimant_id": pid}}
        )
    await log_audit(
        user["id"], "CREATE", "claimant", pid, f"Claimant created: {body.label}"
    )
    doc.pop("_id", None)
    return doc


@api.put("/claimants/{cid}")
async def update_claimant(cid: str, body: ProfileIn, user=Depends(get_current_user)):
    existing = await db.profiles.find_one(
        {"id": cid, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.profiles.update_one({"id": cid, "user_id": user["id"]}, {"$set": update})
    diff = diff_dict(existing, update, list(body.model_dump().keys()))
    await log_audit(
        user["id"], "UPDATE", "claimant", cid, f"Claimant '{body.label}' — {diff}"
    )
    return {**existing, **update}


@api.delete("/claimants/{cid}")
async def delete_claimant(cid: str, user=Depends(get_current_user)):
    res = await db.profiles.delete_one({"id": cid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await db.benefit_weeks.delete_many({"claimant_id": cid, "user_id": user["id"]})
    await db.contacts.delete_many({"claimant_id": cid, "user_id": user["id"]})
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "active_claimant_id": 1})
    if u and u.get("active_claimant_id") == cid:
        # Reassign to any remaining claimant or clear
        nxt = await db.profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"active_claimant_id": nxt["id"] if nxt else None}},
        )
    await log_audit(
        user["id"],
        "DELETE",
        "claimant",
        cid,
        "Claimant + all its weeks/contacts deleted",
    )
    return {"ok": True}


@api.post("/claimants/{cid}/set-active")
async def set_active_claimant(cid: str, user=Depends(get_current_user)):
    p = await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_claimant_id": cid}})
    await log_audit(
        user["id"],
        "SWITCH",
        "claimant",
        cid,
        f"Switched to claimant: {p.get('label', '')}",
    )
    return {"ok": True, "active_id": cid}


# ============== Benefit Weeks ==============
@api.get("/benefit-weeks")
async def list_weeks(user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    q = {"user_id": user["id"]}
    if cid:
        q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    weeks = (
        await db.benefit_weeks.find(q, {"_id": 0}).sort("week_start", -1).to_list(1000)
    )
    # Attach contact count for each
    for w in weeks:
        w["contact_count"] = await db.contacts.count_documents(
            {"benefit_week_id": w["id"]}
        )
    return weeks


@api.post("/benefit-weeks")
async def create_week(body: BenefitWeekIn, user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    wid = str(uuid.uuid4())
    doc = {
        "id": wid,
        "user_id": user["id"],
        "claimant_id": cid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
    }
    await db.benefit_weeks.insert_one(doc)
    await log_audit(
        user["id"],
        "CREATE",
        "benefit_week",
        wid,
        f"Week {body.week_start} – {body.week_end}",
    )
    doc.pop("_id", None)
    return doc


@api.get("/benefit-weeks/{wid}")
async def get_week(wid: str, user=Depends(get_current_user)):
    w = await db.benefit_weeks.find_one({"id": wid, "user_id": user["id"]}, {"_id": 0})
    if not w:
        raise HTTPException(status_code=404, detail="Not found")
    return w


@api.put("/benefit-weeks/{wid}")
async def update_week(wid: str, body: BenefitWeekIn, user=Depends(get_current_user)):
    existing = await db.benefit_weeks.find_one(
        {"id": wid, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()
    await db.benefit_weeks.update_one(
        {"id": wid, "user_id": user["id"]}, {"$set": update}
    )
    diff = diff_dict(existing, update, ["week_start", "week_end", "notes", "certified"])
    await log_audit(
        user["id"],
        "UPDATE",
        "benefit_week",
        wid,
        f"Week {body.week_start}–{body.week_end} — {diff}",
    )
    w = await db.benefit_weeks.find_one({"id": wid}, {"_id": 0})
    return w


@api.delete("/benefit-weeks/{wid}")
async def delete_week(wid: str, user=Depends(get_current_user)):
    res = await db.benefit_weeks.delete_one({"id": wid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await db.contacts.delete_many({"benefit_week_id": wid, "user_id": user["id"]})
    await log_audit(
        user["id"], "DELETE", "benefit_week", wid, "Week deleted (cascaded contacts)"
    )
    return {"ok": True}


# ============== Work Search Contacts ==============
@api.get("/contacts")
async def list_contacts(week_id: Optional[str] = None, user=Depends(get_current_user)):
    query = {"user_id": user["id"]}
    if week_id:
        query["benefit_week_id"] = week_id
    else:
        cid = await get_active_claimant_id(user["id"])
        if cid:
            query["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    items = (
        await db.contacts.find(query, {"_id": 0}).sort("contact_date", -1).to_list(5000)
    )
    return items


@api.post("/contacts")
async def create_contact(body: ContactIn, user=Depends(get_current_user)):
    # Derive claimant_id from the week
    w = await db.benefit_weeks.find_one(
        {"id": body.benefit_week_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")
    cid = str(uuid.uuid4())
    doc = {
        "id": cid,
        "user_id": user["id"],
        "claimant_id": w.get("claimant_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
    }
    await db.contacts.insert_one(doc)
    await log_audit(
        user["id"], "CREATE", "contact", cid, f"Contact: {body.employer_name}"
    )
    doc.pop("_id", None)
    return doc


@api.put("/contacts/{cid}")
async def update_contact(cid: str, body: ContactIn, user=Depends(get_current_user)):
    existing = await db.contacts.find_one(
        {"id": cid, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()
    await db.contacts.update_one({"id": cid, "user_id": user["id"]}, {"$set": update})
    keys = [
        "contact_date",
        "employer_name",
        "employer_address",
        "contact_method",
        "type_of_work",
        "position_applied",
        "person_contacted",
        "result",
        "source_url",
    ]
    diff = diff_dict(existing, update, keys)
    await log_audit(
        user["id"], "UPDATE", "contact", cid, f"{body.employer_name} — {diff}"
    )
    c = await db.contacts.find_one({"id": cid}, {"_id": 0})
    return c


@api.delete("/contacts/{cid}")
async def delete_contact(cid: str, user=Depends(get_current_user)):
    res = await db.contacts.delete_one({"id": cid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(user["id"], "DELETE", "contact", cid, "Contact deleted")
    return {"ok": True}


# ============== Audit Log ==============
@api.get("/audit-log")
async def get_audit(
    q: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    limit: int = 2000,
    user=Depends(get_current_user),
):
    query = {"user_id": user["id"]}
    if action and action != "ALL":
        query["action"] = action
    if entity and entity != "ALL":
        query["entity"] = entity
    if q:
        query["detail"] = {"$regex": q, "$options": "i"}
    items = (
        await db.audit_log.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .to_list(min(max(limit, 1), 5000))
    )
    return items


# ============== Import: CSV ==============
@api.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    week_id: str = Form(...),
    user=Depends(get_current_user),
):
    # Verify the benefit week exists for user
    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_CSV_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"CSV file too large (max {MAX_CSV_IMPORT_BYTES // 1024} KB)",
        )
    raw = raw_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    inserted = 0
    rows_out = []
    for row_num, row in enumerate(reader, start=1):
        if row_num > MAX_CSV_IMPORT_ROWS:
            break
        lc = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        contact = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "benefit_week_id": week_id,
            "claimant_id": w.get("claimant_id"),
            "contact_date": lc.get("date")
            or lc.get("contact_date")
            or lc.get("date applied")
            or w["week_start"],
            "employer_name": lc.get("employer")
            or lc.get("company")
            or lc.get("employer_name")
            or lc.get("company name")
            or "",
            "employer_address": lc.get("address") or lc.get("location") or "",
            "contact_method": (
                lc.get("method") or lc.get("contact_method") or "Online"
            ).title(),
            "type_of_work": lc.get("type_of_work") or lc.get("type") or "",
            "position_applied": lc.get("position")
            or lc.get("job_title")
            or lc.get("title")
            or "",
            "person_contacted": lc.get("contact") or lc.get("person_contacted") or "",
            "result": lc.get("result") or lc.get("status") or "Applied",
            "source_url": lc.get("url") or lc.get("link") or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if contact["contact_method"] not in [
            "In Person",
            "Phone",
            "Email",
            "Online",
            "Mail",
            "Other",
        ]:
            contact["contact_method"] = "Online"
        if contact["employer_name"]:
            await db.contacts.insert_one(contact)
            contact.pop("_id", None)
            rows_out.append(contact)
            inserted += 1
    await log_audit(
        user["id"],
        "IMPORT_CSV",
        "contact",
        week_id,
        f"Imported {inserted} contacts via CSV",
    )
    return {"inserted": inserted, "contacts": rows_out}


# ============== Import: Screenshot OCR (AI Vision) ==============
@api.post("/import/screenshot")
async def import_screenshot(
    file: UploadFile = File(...),
    week_id: str = Form(...),
    user=Depends(get_current_user),
):
    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")

    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(img_bytes) > MAX_SCREENSHOT_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large (max {MAX_SCREENSHOT_IMPORT_BYTES // (1024 * 1024)} MB)",
        )

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_SCREENSHOT_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Upload a PNG, JPEG, or WEBP screenshot.",
        )

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    prompt = (
        "You extract job posting details from screenshots of job boards like Indeed, LinkedIn, "
        "ZipRecruiter, Glassdoor. Output STRICT JSON only, no prose, no markdown. "
        "Extract job(s) from this screenshot. Return JSON: "
        '{"jobs":[{"employer_name":"","position_applied":"","employer_address":"",'
        '"contact_method":"Online","type_of_work":"","contact_date":"YYYY-MM-DD","source_url":"","result":"Applied"}]}. '
        f"If date unclear use {w['week_start']}. If multiple jobs visible include each as an entry."
    )

    import io as _io

    import PIL.Image

    try:
        pil_image = PIL.Image.open(_io.BytesIO(img_bytes))
        pil_image.load()  # force decode now so malformed/oversized images fail here
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read image file")
    if pil_image.width * pil_image.height > MAX_SCREENSHOT_PIXELS:
        raise HTTPException(status_code=400, detail="Image resolution too large")

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.generate_content([prompt, pil_image])
        )
        response = response.text
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vision extraction failed: {e}")

    # Parse JSON from response
    import json
    import re

    text = str(response)
    # Strip code fences if present
    m = re.search(r"\{[\s\S]*\}", text)
    json_str = m.group(0) if m else text
    try:
        data = json.loads(json_str)
    except Exception:
        data = {"jobs": []}

    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    inserted = []
    for j in jobs:
        if not isinstance(j, dict) or not j.get("employer_name"):
            continue
        method = (j.get("contact_method") or "Online").title()
        if method not in ["In Person", "Phone", "Email", "Online", "Mail", "Other"]:
            method = "Online"
        contact = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "benefit_week_id": week_id,
            "claimant_id": w.get("claimant_id"),
            "contact_date": j.get("contact_date") or w["week_start"],
            "employer_name": j.get("employer_name", ""),
            "employer_address": j.get("employer_address", "") or "",
            "contact_method": method,
            "type_of_work": j.get("type_of_work", "") or "",
            "position_applied": j.get("position_applied", "") or "",
            "person_contacted": j.get("person_contacted", "") or "",
            "result": j.get("result", "Applied") or "Applied",
            "source_url": j.get("source_url", "") or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.contacts.insert_one(contact)
        contact.pop("_id", None)
        inserted.append(contact)

    await log_audit(
        user["id"],
        "IMPORT_OCR",
        "contact",
        week_id,
        f"Imported {len(inserted)} contacts via screenshot OCR",
    )
    return {"inserted": len(inserted), "contacts": inserted, "raw": text[:500]}


# ============== Reports (PDF) ==============
@api.get("/reports/benefit-week/{week_id}")
async def report_pdf(week_id: str, user=Depends(get_current_user)):
    import io
    from pypdf import PdfReader, PdfWriter

    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Week not found")

    contacts = (
        await db.contacts.find({"benefit_week_id": week_id})
        .sort("contact_date", 1)
        .to_list(30)
    )

    claimant = await db.profiles.find_one(
        {"id": w.get("claimant_id"), "user_id": user["id"]}
    )
    claimant_name = (
        claimant.get("full_name", "") if claimant else user.get("full_name", "")
    )
    claimant_id = claimant.get("claimant_id", "") if claimant else ""

    name_parts = claimant_name.strip().split()
    first = name_parts[0] if len(name_parts) >= 1 else ""
    last = name_parts[-1] if len(name_parts) >= 2 else ""
    mi = name_parts[1][0] if len(name_parts) >= 3 else ""

    week_end = w.get("week_end", "")
    if hasattr(week_end, "strftime"):
        week_end = week_end.strftime("%m/%d/%Y")

    # == Exact field names from the PDF ====================
    field_values = {
        "Last Name": last,
        "First Name": first,
        "Middle Initial": mi,
        "ID or SSN": claimant_id,
    }

    # The PDF has 5 week-sections; we only fill Week Ending 1 (one week per report)
    field_values["Week Ending 1"] = week_end

    # Row letters a-e, one section (week 1), up to 5 contacts
    row_letters = ["a", "b", "c", "d", "e"]
    for i, c in enumerate(contacts[:5]):
        row = row_letters[i]
        cdate = c.get("contact_date", "")
        if hasattr(cdate, "strftime"):
            cdate = cdate.strftime("%m/%d/%Y")

        employer = c.get("employer_name", "")
        address = c.get("employer_address", "")
        name_addr = f"{employer}\n{address}".strip() if address else employer

        field_values[f"Contact Date 1{row}"]     = str(cdate)
        field_values[f"Name and Address 1{row}"] = name_addr
        field_values[f"Person Contacted 1{row}"] = c.get("person_contacted", "")
        field_values[f"Method of Contact 1{row}"]= c.get("contact_method", "")
        field_values[f"Type of Work 1{row}"]     = c.get("type_of_work", "")
        field_values[f"Results 1{row}"]          = c.get("result", "")

    # == Fill the form ===============================
    try:
        template_path = ROOT_DIR / "assets" / "ADJ034F.pdf"
        if not template_path.exists():
            raise HTTPException(
                status_code=500,
                detail="State form template not found in assets/ADJ034F.pdf",
            )

        reader = PdfReader(str(template_path))
        writer = PdfWriter()
        writer.append(reader)
        writer.update_page_form_field_values(writer.pages[0], field_values)
        writer.set_need_appearances_writer()

        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)

        filename = f"WorkSearch_{week_end}.pdf".replace("/", "-")
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")


# ============== Dashboard summary ==============
@api.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    week_q = {"user_id": user["id"]}
    contact_q = {"user_id": user["id"]}
    if cid:
        week_q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
        contact_q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    weeks = await db.benefit_weeks.count_documents(week_q)
    contacts = await db.contacts.count_documents(contact_q)
    compliant = 0
    non_compliant = 0
    recent = (
        await db.benefit_weeks.find(week_q, {"_id": 0})
        .sort("week_start", -1)
        .to_list(100)
    )
    for w in recent:
        n = await db.contacts.count_documents({"benefit_week_id": w["id"]})
        if n >= 3:
            compliant += 1
        else:
            non_compliant += 1
    profile = None
    if cid:
        profile = await db.profiles.find_one(
            {"id": cid, "user_id": user["id"]}, {"_id": 0}
        )
    return {
        "total_weeks": weeks,
        "total_contacts": contacts,
        "compliant_weeks": compliant,
        "non_compliant_weeks": non_compliant,
        "profile_complete": bool(
            profile and profile.get("first_name") and profile.get("last_name")
        ),
        "active_claimant_id": cid,
    }


# ============== CSV Export ==============
@api.get("/contacts/export.csv")
async def export_contacts_csv(
    week_id: Optional[str] = None, user=Depends(get_current_user)
):
    q = {"user_id": user["id"]}
    if week_id:
        q["benefit_week_id"] = week_id
    else:
        cid = await get_active_claimant_id(user["id"])
        if cid:
            q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    contacts = (
        await db.contacts.find(q, {"_id": 0}).sort("contact_date", 1).to_list(10000)
    )
    buf = io.StringIO()
    fields = [
        "contact_date",
        "employer_name",
        "employer_address",
        "contact_method",
        "position_applied",
        "type_of_work",
        "person_contacted",
        "result",
        "source_url",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for c in contacts:
        writer.writerow(c)
    buf.seek(0)
    await log_audit(
        user["id"],
        "EXPORT_CSV",
        "contact",
        week_id,
        f"Exported {len(contacts)} contacts to CSV",
    )
    fname = f"contacts_{week_id or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# ============== Password Reset ==============
@api.post("/auth/forgot-password")
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
                "expires_at": expires,  # BSON datetime — TTL index will auto-clean
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
            user["id"],
            "FORGOT_PW",
            "user",
            user["id"],
            f"Reset link sent (mailgun={'ok' if sent else 'fail'})",
        )
    return {"ok": True, "message": "If that email exists, a reset link has been sent."}


@api.post("/auth/reset-password")
async def reset_password(body: ResetPwIn):
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
    await log_audit(
        rec["user_id"],
        "RESET_PW",
        "user",
        rec["user_id"],
        "Password reset via email link",
    )
    return {"ok": True}


# ============== Admin (case-worker) ==============
async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@api.get("/admin/users")
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


@api.get("/admin/users/{uid}")
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
        w["contact_count"] = await db.contacts.count_documents(
            {"benefit_week_id": w["id"]}
        )
    return {"user": user, "claimants": claimants, "weeks": weeks}


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

        <!-- Header -->
        <div style="background:#0033A0; padding:16px 24px; border-radius:4px 4px 0 0;">
          <div style="display:flex; align-items:center; gap:12px;">
            <div style="background:#fff; color:#0033A0; font-weight:900; font-size:18px; width:36px; height:36px; display:inline-flex; align-items:center; justify-content:center; border-radius:4px; font-family:'Chivo',Arial,sans-serif;">IL</div>
            <div>
              <div style="color:#fff; font-family:'Chivo',Arial,sans-serif; font-weight:900; font-size:16px; letter-spacing:-0.01em;">Illinois UI Job Search Tracker</div>
              <div style="color:#93afd4; font-size:11px; letter-spacing:0.08em; text-transform:uppercase;">Work Search Compliance</div>
            </div>
          </div>
        </div>

        <!-- Body -->
        <div style="background:#ffffff; border:1px solid #D4D4D8; border-top:none; border-radius:0 0 4px 4px; padding:24px;" class="email-body">
          <h2 style="margin:0 0 16px; font-family:'Chivo',Arial,sans-serif; font-weight:900; color:#09090B; letter-spacing:-0.01em;" class="email-text">{title}</h2>
          <div style="color:#09090B;" class="email-text">{body_html}</div>

          <!-- Login CTA -->
          <div style="margin:28px 0 20px;">
            <a href="{frontend_url}" class="login-btn"
               style="display:inline-block; background:#0033A0; color:#ffffff; padding:12px 24px; text-decoration:none; font-weight:600; font-size:14px; border-radius:2px;">
              Log In to Illinois UI Tracker
            </a>
          </div>

          <!-- Footer -->
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
    # Find this week's Sunday (Python: Monday=0…Sunday=6)
    days_since_sun = (now.weekday() + 1) % 7
    sunday = (now - timedelta(days=days_since_sun)).date()
    saturday = sunday + timedelta(days=6)
    return sunday.isoformat(), saturday.isoformat()


async def _send_user_reminder(user: dict, kind: str):
    """kind in: 'sunday','wednesday','friday','saturday'"""
    # Defense in depth: only send outbound mail/SMS for accounts that have
    # proven ownership of their email. Registration no longer issues a
    # session token before verification, but this keeps it true even if a
    # token were ever minted for an unverified account some other way.
    if not user.get("email_verified", False):
        return 0
    # iterate claimants that have reminders_enabled
    claimants = await db.profiles.find(
        {"user_id": user["id"], "reminders_enabled": {"$ne": False}}, {"_id": 0}
    ).to_list(50)
    if not claimants:
        return 0
    sun, sat = _current_week_bounds()
    sent = 0
    for c in claimants:
        # Find this week's matching benefit week
        w = await db.benefit_weeks.find_one(
            {
                "user_id": user["id"],
                "claimant_id": c["id"],
                "week_start": sun,
                "week_end": sat,
            },
            {"_id": 0},
        )
        contacts_count = 0
        contacts_list = []
        if w:
            contacts_list = await db.contacts.find(
                {"benefit_week_id": w["id"]}, {"_id": 0}
            ).to_list(50)
            contacts_count = len(contacts_list)

        # reminder_email/name/employer fields are user-controlled (set via
        # the profile/contact forms); escape before interpolating into the
        # HTML email body to prevent HTML/markup injection in outbound mail.
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
                position = html.escape(
                    str(x.get("position_applied", "") or x.get("type_of_work", ""))
                )
                return f"<li>{date_} — {employer} ({position})</li>"
            return f"<li>{date_} — {employer}</li>"

        if kind == "sunday":
            title = "New Benefit Week Starting"
            body = f"<p>Hi {name}, your new benefit week ({sun} → {sat}) starts today. Aim for at least 3 work-search contacts this week.</p>"
        elif kind == "wednesday":
            if contacts_count >= 3:
                continue
            title = (
                f"Mid-Week Check — {deficit} contact{'s' if deficit != 1 else ''} to go"
            )
            body = f"<p>Hi {name}, you're at <b>{contacts_count} / 3</b> contacts for the week {sun} → {sat}. Keep going!</p>"
        elif kind == "friday":
            title = f"Friday Reminder — {contacts_count} / 3 contacts logged"
            list_html = "".join(
                _contact_line(x, with_position=True) for x in contacts_list
            )
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
            await log_audit(
                user["id"],
                f"REMINDER_{kind.upper()}",
                "claimant",
                c["id"],
                f"Email sent to {to_email}",
            )

        # SMS reminder (optional + rate-limited + only if phone is verified)
        if c.get("sms_enabled") and c.get("sms_phone") and c.get("sms_verified"):
            sms_text = f"[IL UI Tracker] {title}: {contacts_count}/3 contacts for week {sun}–{sat}."
            if kind == "friday" and contacts_count < 3:
                sms_text += f" Log {deficit} more by Sat."
            ok_sms, reason = await send_sms_rate_limited(
                c["sms_phone"], sms_text, c["id"]
            )
            if ok_sms:
                await log_audit(
                    user["id"],
                    f"SMS_{kind.upper()}",
                    "claimant",
                    c["id"],
                    f"SMS sent to {c['sms_phone']}",
                )
            elif reason.startswith("rate-limited"):
                await log_audit(
                    user["id"], "SMS_SKIPPED", "claimant", c["id"], f"{kind}: {reason}"
                )
    return sent


@api.post("/reminders/test")
@rate_limit(RATE_LIMIT_REMINDER_TEST)
async def reminder_test(
    request: Request, kind: str = "friday", user=Depends(get_current_user)
):
    if kind not in ("sunday", "wednesday", "friday", "saturday"):
        raise HTTPException(
            status_code=400, detail="kind must be sunday|wednesday|friday|saturday"
        )
    n = await _send_user_reminder(user, kind)
    return {"sent": n, "kind": kind}


async def _broadcast_reminders(kind: str):
    cursor = db.users.find({}, {"_id": 0})
    async for u in cursor:
        try:
            await _send_user_reminder(u, kind)
        except Exception as e:
            logging.warning(f"Reminder {kind} failed for {u.get('email')}: {e}")


# ============== Dashboard Trend (last N weeks) ==============
@api.get("/dashboard/trend")
async def dashboard_trend(weeks: int = 12, user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    q = {"user_id": user["id"]}
    if cid:
        q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    recent = (
        await db.benefit_weeks.find(q, {"_id": 0})
        .sort("week_start", -1)
        .to_list(min(max(weeks, 1), 52))
    )
    recent.reverse()
    out = []
    for w in recent:
        n = await db.contacts.count_documents({"benefit_week_id": w["id"]})
        out.append(
            {
                "week_start": w["week_start"],
                "week_end": w["week_end"],
                "contacts": n,
                "target": 3,
                "compliant": n >= 3,
            }
        )
    return out


# ============== Invite Codes (Admin) ==============
@api.post("/admin/invites")
async def create_invite(body: InviteCreate, admin=Depends(require_admin)):
    code = secrets.token_urlsafe(12)
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(
            status_code=400, detail="A user with that email already exists"
        )
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
    await log_audit(
        admin["id"], "INVITE_CREATE", "invite", code, f"Invite for {body.email}"
    )
    invite_link = (
        f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{code}"
    )
    # Send email
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


@api.get("/admin/invites")
async def list_invites(admin=Depends(require_admin)):
    items = await db.invites.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for it in items:
        it["invite_link"] = (
            f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{it['code']}"
        )
    return items


@api.delete("/admin/invites/{code}")
async def revoke_invite(code: str, admin=Depends(require_admin)):
    res = await db.invites.delete_one({"code": code})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(admin["id"], "INVITE_REVOKE", "invite", code, "Invite revoked")
    return {"ok": True}


@api.get("/invite/{code}")
async def get_invite(code: str):
    """Public endpoint — returns invite details if valid (no auth)."""
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


@api.post("/invite/redeem")
async def redeem_invite(body: InviteRedeem):
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
    # Create user + claimant
    if await db.users.find_one({"email": inv["email"]}):
        raise HTTPException(
            status_code=400, detail="Account already exists with this email"
        )
    uid = str(uuid.uuid4())
    await db.users.insert_one(
        {
            "id": uid,
            "email": inv["email"],
            "name": body.name,
            "password_hash": hash_password(body.password),
            "role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "invited_by": inv.get("created_by"),
        }
    )
    pid = str(uuid.uuid4())
    await db.profiles.insert_one(
        {
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
        }
    )
    await db.users.update_one({"id": uid}, {"$set": {"active_claimant_id": pid}})
    await db.invites.update_one(
        {"code": body.code},
        {
            "$set": {
                "used": True,
                "used_at": datetime.now(timezone.utc),
                "redeemed_user_id": uid,
            }
        },
    )
    await log_audit(
        uid,
        "REGISTER_INVITE",
        "user",
        uid,
        f"Invited account created from {inv.get('created_by')}",
    )
    token = create_token(uid, inv["email"])
    return {
        "token": token,
        "user": {"id": uid, "email": inv["email"], "name": body.name, "role": "user"},
    }


# ============== SMS Phone OTP Verification ==============
class OtpSendIn(BaseModel):
    claimant_id: str
    phone: str


class OtpVerifyIn(BaseModel):
    claimant_id: str
    code: str


@api.post("/sms/send-otp")
async def sms_send_otp(body: OtpSendIn, user=Depends(get_current_user)):
    c = await db.profiles.find_one(
        {"id": body.claimant_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not c:
        raise HTTPException(status_code=404, detail="Claimant not found")
    phone = body.phone.strip()
    if not phone.startswith("+"):
        raise HTTPException(
            status_code=400, detail="Phone must be E.164 (e.g. +13125550100)"
        )
    # Generate 6-digit code
    import random

    code = f"{random.randint(0, 999999):06d}"
    await db.otp_codes.insert_one(
        {
            "claimant_id": body.claimant_id,
            "user_id": user["id"],
            "phone": phone,
            "code": code,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            "used": False,
            "created_at": datetime.now(timezone.utc),
        }
    )
    msg = f"Illinois UI Tracker verification code: {code} (expires in 10 minutes)"
    sent, reason = await send_sms_rate_limited(phone, msg, body.claimant_id)
    await log_audit(
        user["id"],
        "OTP_SEND",
        "claimant",
        body.claimant_id,
        f"OTP to {phone}: {'sent' if sent else reason}",
    )
    if not sent:
        raise HTTPException(
            status_code=502,
            detail=f"Could not send SMS ({reason}). Make sure the number is verified in Twilio for trial accounts.",
        )
    return {"ok": True, "expires_in_minutes": 10}


@api.post("/sms/verify-otp")
async def sms_verify_otp(body: OtpVerifyIn, user=Depends(get_current_user)):
    rec = await db.otp_codes.find_one(
        {"claimant_id": body.claimant_id, "user_id": user["id"], "used": False},
        sort=[("created_at", -1)],
    )
    if not rec:
        raise HTTPException(
            status_code=400, detail="No active OTP found. Request a new code."
        )
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
        {
            "$set": {
                "sms_verified": True,
                "sms_phone": rec["phone"],
                "sms_verified_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    await log_audit(
        user["id"],
        "OTP_VERIFY",
        "claimant",
        body.claimant_id,
        f"Phone {rec['phone']} verified",
    )
    return {"ok": True, "phone": rec["phone"]}


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

    timestamp = (
        timestamp or payload.get("timestamp") or payload.get("signature[timestamp]")
    )
    token = token or payload.get("token") or payload.get("signature[token]")
    signature = (
        signature or payload.get("signature") or payload.get("signature[signature]")
    )

    if not timestamp or not token or not signature:
        raise HTTPException(status_code=400, detail="Mailgun webhook signature missing")

    secret = os.environ.get("MAILGUN_API_KEY", "")
    if not secret:
        logging.warning("Mailgun webhook signature verification is not configured")
        raise HTTPException(
            status_code=503, detail="Mailgun webhook verification is not configured"
        )

    expected = hmac.new(
        secret.encode("utf-8"), f"{timestamp}{token}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, str(signature)):
        raise HTTPException(status_code=403, detail="Invalid Mailgun webhook signature")


@api.post("/webhooks/mailgun")
async def mailgun_webhook(request: Request):
    payload = await _parse_mailgun_webhook(request)
    _verify_mailgun_signature(payload)
    data = payload.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    event_type = data.get("event") or payload.get("type", "")
    to_emails = (
        data.get("recipient")
        or data.get("recipients")
        or data.get("message", {}).get("headers", {}).get("to")
        or []
    )
    if isinstance(to_emails, str):
        if "," in to_emails:
            to_emails = [addr.strip() for addr in to_emails.split(",") if addr.strip()]
        else:
            to_emails = [to_emails.strip()]
    await db.email_events.insert_one(
        {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "to": to_emails,
            "received_at": datetime.now(timezone.utc),
            "raw": data,
        }
    )
    if event_type in (
        "email.bounced",
        "email.complained",
        "bounced",
        "complained",
        "complaint",
    ):
        for addr in to_emails:
            await db.profiles.update_many(
                {"reminder_email": addr},
                {
                    "$set": {
                        "reminders_enabled": False,
                        "email_bounced": True,
                        "email_bounced_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
            users_with_email = await db.users.find(
                {"email": addr.lower() if isinstance(addr, str) else ""},
                {"_id": 0, "id": 1},
            ).to_list(20)
            for u in users_with_email:
                await db.profiles.update_many(
                    {"user_id": u["id"], "reminder_email": ""},
                    {"$set": {"reminders_enabled": False, "email_bounced": True}},
                )
    return {"ok": True}


@api.get("/admin/email-events")
async def admin_email_events(admin=Depends(require_admin)):
    items = (
        await db.email_events.find({}, {"_id": 0}).sort("received_at", -1).to_list(500)
    )
    for it in items:
        if isinstance(it.get("received_at"), datetime):
            it["received_at"] = it["received_at"].isoformat()
    return items


# ============== Bulk Invite (Admin) ==============
class BulkInviteIn(BaseModel):
    csv_text: str = ""  # CSV: email,claimant_label,note (header required)
    note: str = ""


@api.post("/admin/invites/bulk")
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
        link = (
            f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{code}"
        )
        await send_email(
            email,
            "You're invited to Illinois UI Tracker",
            _reminder_html(
                "You're invited",
                f"<p>A case worker invited you. <a href='{link}'>Accept invite</a></p><p style='font-size:11px; color:#52525B; word-break:break-all;'>{link}</p>",
            ),
        )
        created.append({"email": email, "code": code, "invite_link": link})
    await log_audit(
        admin["id"],
        "INVITE_BULK",
        "invite",
        None,
        f"Created {len(created)}, skipped {len(skipped)}",
    )
    return {"created": created, "skipped": skipped}


# ============== Integration Status (Admin) ==============
@api.get("/admin/integrations/status")
async def integrations_status(admin=Depends(require_admin)):
    has_mailgun = bool(os.environ.get("MAILGUN_API_KEY"))
    has_twilio = bool(
        os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and os.environ.get("TWILIO_FROM_NUMBER")
    )
    domain = os.environ.get("MAILGUN_VERIFIED_DOMAIN", "")
    from_addr = os.environ.get("MAILGUN_FROM", "")
    return {
        "mailgun": {
            "configured": has_mailgun,
            "from": from_addr,
            "verified_domain": domain,
            "fallback_from": os.environ.get(
                "MAILGUN_FALLBACK_FROM", "onboarding@mailgun.com"
            ),
            "dns_records_url": "https://app.mailgun.com/mg/sending/domains",
        },
        "twilio": {
            "configured": has_twilio,
            "from_number": os.environ.get("TWILIO_FROM_NUMBER", ""),
        },
    }


# ============== Health ==============
@api.get("/")
async def root():
    return {"app": "Illinois UI Job Search Tracker", "ok": True}


# ============== Startup ==============
scheduler: Optional[AsyncIOScheduler] = None


@app.on_event("startup")
async def on_startup():
    global scheduler
    await db.users.create_index("email", unique=True)
    await db.benefit_weeks.create_index("user_id")
    await db.contacts.create_index([("user_id", 1), ("benefit_week_id", 1)])
    await db.audit_log.create_index([("user_id", 1), ("timestamp", -1)])
    await db.profiles.create_index("user_id")
    # TTL index on password_resets.expires_at (BSON datetime auto-cleanup)
    try:
        await db.password_resets.create_index("expires_at", expireAfterSeconds=0)
    except Exception as e:
        logging.info(f"password_resets TTL index: {e}")
    try:
        await db.invites.create_index("expires_at", expireAfterSeconds=0)
        await db.invites.create_index("code", unique=True)
    except Exception as e:
        logging.info(f"invites indexes: {e}")

    # Seed demo user only when explicitly enabled
    demo_user_enabled = os.environ.get("ENABLE_DEMO_USER", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    demo_email = os.environ.get("DEMO_USER_EMAIL", "demo@illinoistracker.test").lower()
    demo_password = os.environ.get("DEMO_USER_PASSWORD", "Demo1234!")
    if demo_user_enabled:
        existing = await db.users.find_one({"email": demo_email})
        if not existing:
            uid = str(uuid.uuid4())
            await db.users.insert_one(
                {
                    "id": uid,
                    "email": demo_email,
                    "name": "Demo Claimant",
                    "password_hash": hash_password(demo_password),
                    "role": "user",
                    # Seeded accounts skip the email-verification gate so they
                    # can actually log in.
                    "email_verified": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            pid = str(uuid.uuid4())
            await db.profiles.insert_one(
                {
                    "id": pid,
                    "user_id": uid,
                    "label": "Primary",
                    "first_name": "Demo",
                    "last_name": "Claimant",
                    "middle_initial": "A",
                    "claimant_id": "1234567",
                    "address": "100 W Randolph St",
                    "city": "Chicago",
                    "state": "IL",
                    "zip_code": "60601",
                    "phone": "312-555-1212",
                    "occupation": "Software Developer",
                    "reminders_enabled": True,
                    "reminder_email": "democlaimant@example.com",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            await db.users.update_one(
                {"id": uid}, {"$set": {"active_claimant_id": pid}}
            )
        else:
            update = {"email_verified": True}
            if not verify_password(demo_password, existing["password_hash"]):
                update["password_hash"] = hash_password(demo_password)
            await db.users.update_one({"email": demo_email}, {"$set": update})
    else:
        logging.info(
            "Demo user seeding disabled. Set ENABLE_DEMO_USER=true to enable it."
        )

    # Seed admin (case-worker) account only when configured explicitly
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_pw = os.environ.get("ADMIN_PASSWORD", "")
    if admin_email and admin_pw:
        existing_admin = await db.users.find_one({"email": admin_email})
        if not existing_admin:
            await db.users.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "email": admin_email,
                    "name": "Admin / Case Worker",
                    "password_hash": hash_password(admin_pw),
                    "role": "admin",
                    "email_verified": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        elif existing_admin.get("role") == "admin" and not verify_password(
            admin_pw, existing_admin["password_hash"]
        ):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_password(admin_pw)}},
            )
        elif existing_admin.get("role") != "admin":
            logging.warning(
                f"Configured ADMIN_EMAIL {admin_email} already exists as non-admin. Skipping admin seed."
            )
    else:
        logging.warning(
            "ADMIN_EMAIL and ADMIN_PASSWORD are not configured; no admin account will be created automatically."
        )

    # Data migration: backfill claimant_id and active_claimant_id
    async for u in db.users.find(
        {}, {"_id": 0, "id": 1, "active_claimant_id": 1, "role": 1}
    ):
        if u.get("role") == "admin":
            continue
        active = u.get("active_claimant_id")
        if not active:
            p = await db.profiles.find_one({"user_id": u["id"]}, {"_id": 0, "id": 1})
            if p:
                active = p["id"]
                await db.users.update_one(
                    {"id": u["id"]}, {"$set": {"active_claimant_id": active}}
                )
        if active:
            await db.benefit_weeks.update_many(
                {"user_id": u["id"], "claimant_id": {"$exists": False}},
                {"$set": {"claimant_id": active}},
            )
            await db.contacts.update_many(
                {"user_id": u["id"], "claimant_id": {"$exists": False}},
                {"$set": {"claimant_id": active}},
            )

    # Reminder scheduler
    if os.environ.get("MAILGUN_API_KEY"):
        try:
            scheduler = AsyncIOScheduler(timezone=pytz.timezone("America/Chicago"))
            scheduler.add_job(
                _broadcast_reminders,
                CronTrigger(day_of_week="sun", hour=9, minute=0),
                args=["sunday"],
                id="rem_sun",
            )
            scheduler.add_job(
                _broadcast_reminders,
                CronTrigger(day_of_week="wed", hour=9, minute=0),
                args=["wednesday"],
                id="rem_wed",
            )
            scheduler.add_job(
                _broadcast_reminders,
                CronTrigger(day_of_week="fri", hour=9, minute=0),
                args=["friday"],
                id="rem_fri",
            )
            scheduler.add_job(
                _broadcast_reminders,
                CronTrigger(day_of_week="sat", hour=9, minute=0),
                args=["saturday"],
                id="rem_sat",
            )
            scheduler.start()
            logging.info("Reminder scheduler started (America/Chicago)")
        except Exception as e:
            logging.warning(f"Could not start reminder scheduler: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    global scheduler
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
    client.close()


# ============== Health / readiness probes ==============
# Kept off the /api prefix so load balancers and uptime monitors can hit them
# directly. /health/live = process is up; /health/ready = dependencies (Mongo)
# are reachable so the instance can receive traffic.
@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    try:
        await client.admin.command("ping")
        return {"status": "ready", "mongo": "ok"}
    except Exception as e:
        logging.warning(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "mongo": "error"},
        )


app.include_router(api)


# ============== Security headers ==============
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    # HSTS only makes sense behind TLS; enable explicitly in production.
    if os.environ.get("ENABLE_HSTS", "false").lower() in ("1", "true", "yes"):
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains",
        )
    return response


# CORS - allow_origins must be explicit when allow_credentials=True
origins_env = os.environ.get("CORS_ORIGINS", "*")
allow_credentials = True
if origins_env.strip() == "*":
    allow_origins = ["*"]
    allow_credentials = False
else:
    allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_credentials,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
