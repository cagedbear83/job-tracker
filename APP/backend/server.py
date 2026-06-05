from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import io
import csv
import uuid
import jwt
import bcrypt
import logging
import secrets
import pytz
import asyncio
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import requests as http_requests
from twilio.rest import Client as TwilioClient

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch

# ---- DB ----
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# ---- App ----
app = FastAPI(title="Illinois UI Job Search Tracker")
api = APIRouter(prefix="/api")

JWT_ALGO = "HS256"
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")


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


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthOut(BaseModel):
    token: str
    user: UserPublic


class ProfileIn(BaseModel):
    label: str = "Primary"
    first_name: str = ""
    last_name: str = ""
    middle_initial: str = ""
    claimant_id_last4: str = ""
    address: str = ""
    city: str = ""
    state: str = "IL"
    zip_code: str = ""
    phone: str = ""
    occupation: str = ""
    reminders_enabled: bool = True
    reminder_email: str = ""
    sms_enabled: bool = False
    sms_phone: str = ""  # E.164 format e.g. +13125550100
    sms_verified: bool = False


class Profile(ProfileIn):
    id: str
    user_id: str
    updated_at: datetime


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
    week_end: str    # ISO date (Saturday)
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
    contact_method: Literal["In Person", "Phone", "Email", "Online", "Mail", "Other"] = "Online"
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
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_current_user(request: Request) -> dict:
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def log_audit(user_id: str, action: str, entity: str, entity_id: str = None, detail: str = ""):
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
    logging.info(f"MAILGUN DEBUG key={os.environ.get('MAILGUN_API_KEY','MISSING')} domain={os.environ.get('MAILGUN_DOMAIN','MISSING')}")
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
            }
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


async def send_sms_rate_limited(phone: str, body: str, claimant_id: str = "") -> tuple[bool, str]:
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
            return False, f"rate-limited ({int(delta.total_seconds()/60)}m / {SMS_MIN_INTERVAL_MINUTES}m)"
    ok = send_sms(phone, body)
    if ok:
        await db.sms_log.insert_one({
            "phone": phone,
            "claimant_id": claimant_id,
            "body_preview": body[:120],
            "sent_at": datetime.now(timezone.utc),
        })
    return ok, "ok" if ok else "twilio-error"


def to_public_user(u: dict) -> UserPublic:
    return UserPublic(id=u["id"], email=u["email"], name=u.get("name", ""), role=u.get("role", "user"))


# ============== Auth Endpoints ==============
@api.post("/auth/register", response_model=AuthOut)
async def register(body: RegisterIn):
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
    await log_audit(uid, "REGISTER", "user", uid, f"Account created: {email}")
    token = create_token(uid, email)
    return AuthOut(token=token, user=UserPublic(id=uid, email=email, name=body.name, role="user"))


@api.post("/auth/login", response_model=AuthOut)
async def login(body: LoginIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["email"])
    await log_audit(user["id"], "LOGIN", "user", user["id"], f"Login successful")
    return AuthOut(token=token, user=UserPublic(id=user["id"], email=user["email"], name=user.get("name", ""), role=user.get("role", "user")))


@api.post("/auth/logout")
async def logout(user=Depends(get_current_user)):
    await log_audit(user["id"], "LOGOUT", "user", user["id"], "Logout")
    return {"ok": True}


@api.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return UserPublic(id=user["id"], email=user["email"], name=user.get("name", ""), role=user.get("role", "user"))


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
        existing = await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0}) or {}
        update = body.model_dump()
        update["updated_at"] = now
        await db.profiles.update_one({"id": cid, "user_id": user["id"]}, {"$set": update})
        diff = diff_dict(existing, update, list(body.model_dump().keys()))
        await log_audit(user["id"], "UPDATE", "claimant", cid, f"Claimant updated — {diff}")
        return {**existing, **update}
    pid = str(uuid.uuid4())
    doc = {"id": pid, "user_id": user["id"], "updated_at": now, **body.model_dump()}
    await db.profiles.insert_one(doc)
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_claimant_id": pid}})
    await log_audit(user["id"], "CREATE", "claimant", pid, f"Claimant created: {body.label}")
    doc.pop("_id", None)
    return doc


@api.get("/claimants")
async def list_claimants(user=Depends(get_current_user)):
    items = await db.profiles.find({"user_id": user["id"]}, {"_id": 0}).sort("label", 1).to_list(100)
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
        await db.users.update_one({"id": user["id"]}, {"$set": {"active_claimant_id": pid}})
    await log_audit(user["id"], "CREATE", "claimant", pid, f"Claimant created: {body.label}")
    doc.pop("_id", None)
    return doc


@api.put("/claimants/{cid}")
async def update_claimant(cid: str, body: ProfileIn, user=Depends(get_current_user)):
    existing = await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.profiles.update_one({"id": cid, "user_id": user["id"]}, {"$set": update})
    diff = diff_dict(existing, update, list(body.model_dump().keys()))
    await log_audit(user["id"], "UPDATE", "claimant", cid, f"Claimant '{body.label}' — {diff}")
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
        await db.users.update_one({"id": user["id"]}, {"$set": {"active_claimant_id": nxt["id"] if nxt else None}})
    await log_audit(user["id"], "DELETE", "claimant", cid, "Claimant + all its weeks/contacts deleted")
    return {"ok": True}


@api.post("/claimants/{cid}/set-active")
async def set_active_claimant(cid: str, user=Depends(get_current_user)):
    p = await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_claimant_id": cid}})
    await log_audit(user["id"], "SWITCH", "claimant", cid, f"Switched to claimant: {p.get('label','')}")
    return {"ok": True, "active_id": cid}


# ============== Benefit Weeks ==============
@api.get("/benefit-weeks")
async def list_weeks(user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    q = {"user_id": user["id"]}
    if cid:
        q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    weeks = await db.benefit_weeks.find(q, {"_id": 0}).sort("week_start", -1).to_list(1000)
    # Attach contact count for each
    for w in weeks:
        w["contact_count"] = await db.contacts.count_documents({"benefit_week_id": w["id"]})
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
    await log_audit(user["id"], "CREATE", "benefit_week", wid, f"Week {body.week_start} – {body.week_end}")
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
    existing = await db.benefit_weeks.find_one({"id": wid, "user_id": user["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()
    await db.benefit_weeks.update_one({"id": wid, "user_id": user["id"]}, {"$set": update})
    diff = diff_dict(existing, update, ["week_start", "week_end", "notes", "certified"])
    await log_audit(user["id"], "UPDATE", "benefit_week", wid, f"Week {body.week_start}–{body.week_end} — {diff}")
    w = await db.benefit_weeks.find_one({"id": wid}, {"_id": 0})
    return w


@api.delete("/benefit-weeks/{wid}")
async def delete_week(wid: str, user=Depends(get_current_user)):
    res = await db.benefit_weeks.delete_one({"id": wid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await db.contacts.delete_many({"benefit_week_id": wid, "user_id": user["id"]})
    await log_audit(user["id"], "DELETE", "benefit_week", wid, "Week deleted (cascaded contacts)")
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
    items = await db.contacts.find(query, {"_id": 0}).sort("contact_date", -1).to_list(5000)
    return items


@api.post("/contacts")
async def create_contact(body: ContactIn, user=Depends(get_current_user)):
    # Derive claimant_id from the week
    w = await db.benefit_weeks.find_one({"id": body.benefit_week_id, "user_id": user["id"]}, {"_id": 0})
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
    await log_audit(user["id"], "CREATE", "contact", cid, f"Contact: {body.employer_name}")
    doc.pop("_id", None)
    return doc


@api.put("/contacts/{cid}")
async def update_contact(cid: str, body: ContactIn, user=Depends(get_current_user)):
    existing = await db.contacts.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()
    await db.contacts.update_one({"id": cid, "user_id": user["id"]}, {"$set": update})
    keys = ["contact_date", "employer_name", "employer_address", "contact_method",
            "type_of_work", "position_applied", "person_contacted", "result", "source_url"]
    diff = diff_dict(existing, update, keys)
    await log_audit(user["id"], "UPDATE", "contact", cid, f"{body.employer_name} — {diff}")
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
    items = await db.audit_log.find(query, {"_id": 0}).sort("timestamp", -1).to_list(min(max(limit, 1), 5000))
    return items


# ============== Import: CSV ==============
@api.post("/import/csv")
async def import_csv(file: UploadFile = File(...), week_id: str = Form(...), user=Depends(get_current_user)):
    # Verify the benefit week exists for user
    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")
    raw = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    inserted = 0
    rows_out = []
    for row in reader:
        lc = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        contact = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "benefit_week_id": week_id,
            "claimant_id": w.get("claimant_id"),
            "contact_date": lc.get("date") or lc.get("contact_date") or lc.get("date applied") or w["week_start"],
            "employer_name": lc.get("employer") or lc.get("company") or lc.get("employer_name") or lc.get("company name") or "",
            "employer_address": lc.get("address") or lc.get("location") or "",
            "contact_method": (lc.get("method") or lc.get("contact_method") or "Online").title(),
            "type_of_work": lc.get("type_of_work") or lc.get("type") or "",
            "position_applied": lc.get("position") or lc.get("job_title") or lc.get("title") or "",
            "person_contacted": lc.get("contact") or lc.get("person_contacted") or "",
            "result": lc.get("result") or lc.get("status") or "Applied",
            "source_url": lc.get("url") or lc.get("link") or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if contact["contact_method"] not in ["In Person", "Phone", "Email", "Online", "Mail", "Other"]:
            contact["contact_method"] = "Online"
        if contact["employer_name"]:
            await db.contacts.insert_one(contact)
            contact.pop("_id", None)
            rows_out.append(contact)
            inserted += 1
    await log_audit(user["id"], "IMPORT_CSV", "contact", week_id, f"Imported {inserted} contacts via CSV")
    return {"inserted": inserted, "contacts": rows_out}


# ============== Import: Screenshot OCR (AI Vision) ==============
@api.post("/import/screenshot")
async def import_screenshot(file: UploadFile = File(...), week_id: str = Form(...), user=Depends(get_current_user)):
    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")

    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # Save image to temp file (Gemini supports file path)
    import base64, tempfile
    mime = file.content_type or "image/png"
    suffix = ".png" if "png" in mime else (".jpg" if "jpe" in mime or "jpg" in mime else ".png")

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    image_b64 = base64.b64encode(img_bytes).decode()

    prompt = (
        "You extract job posting details from screenshots of job boards like Indeed, LinkedIn, "
        "ZipRecruiter, Glassdoor. Output STRICT JSON only, no prose, no markdown. "
        "Extract job(s) from this screenshot. Return JSON: "
        '{"jobs":[{"employer_name":"","position_applied":"","employer_address":"",'
        '"contact_method":"Online","type_of_work":"","contact_date":"YYYY-MM-DD","source_url":"","result":"Applied"}]}. '
        f"If date unclear use {w['week_start']}. If multiple jobs visible include each as an entry."
    )

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        import PIL.Image, io as _io
        pil_image = PIL.Image.open(_io.BytesIO(img_bytes))
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.generate_content([prompt, pil_image])
        )
        response = response.text
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vision extraction failed: {e}")

    # Parse JSON from response
    import json, re
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

    await log_audit(user["id"], "IMPORT_OCR", "contact", week_id, f"Imported {len(inserted)} contacts via screenshot OCR")
    return {"inserted": len(inserted), "contacts": inserted, "raw": text[:500]}


# ============== Reports (PDF) ==============
@api.get("/reports/benefit-week/{wid}")
async def report_pdf(wid: str, user=Depends(get_current_user)):
    w = await db.benefit_weeks.find_one({"id": wid, "user_id": user["id"]}, {"_id": 0})
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")
    profile = await db.profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    contacts = await db.contacts.find({"benefit_week_id": wid}, {"_id": 0}).sort("contact_date", 1).to_list(1000)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('t', parent=styles['Heading1'], textColor=colors.HexColor("#0033A0"), spaceAfter=4, fontSize=16)
    sub_style = ParagraphStyle('s', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor("#52525B"))
    label_style = ParagraphStyle('l', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#09090B"))
    story = []

    # Logo + Title header
    from reportlab.platypus import Image as RLImage
    logo_path = str(ROOT_DIR / "assets" / "ides-logo.png")
    header_data = []
    try:
        logo = RLImage(logo_path, width=0.85*inch, height=0.85*inch)
        header_data = [[logo,
                        Paragraph("ILLINOIS DEPARTMENT OF EMPLOYMENT SECURITY<br/><font size=9 color='#52525B'>Work Search Record — Benefit Week Report (ADJ034F-style)</font>", title_style)]]
        ht = Table(header_data, colWidths=[1.0*inch, 6.5*inch])
        ht.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
        story.append(ht)
    except Exception:
        story.append(Paragraph("ILLINOIS DEPARTMENT OF EMPLOYMENT SECURITY", title_style))
        story.append(Paragraph("Work Search Record — Benefit Week Report (ADJ034F-style)", sub_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<font color='#DC2626'><b>UNOFFICIAL</b></font> — generated by a third-party tracker; mirrors IDES form structure for personal record-keeping.", sub_style))
    story.append(Spacer(1, 12))

    # Claimant block
    claim_data = [
        ["Claimant Name:", f"{profile.get('first_name','')} {profile.get('middle_initial','')} {profile.get('last_name','')}".strip(),
         "ID (last 4):", profile.get('claimant_id_last4','')],
        ["Address:", f"{profile.get('address','')}, {profile.get('city','')}, {profile.get('state','IL')} {profile.get('zip_code','')}".strip(", "),
         "Phone:", profile.get('phone','')],
        ["Occupation:", profile.get('occupation',''), "Week:", f"{w['week_start']} to {w['week_end']}"],
    ]
    ct = Table(claim_data, colWidths=[1.1*inch, 3.0*inch, 0.9*inch, 2.5*inch])
    ct.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#09090B")),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#D4D4D8")),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F4F4F5")),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F4F4F5")),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(ct)
    story.append(Spacer(1, 14))

    story.append(Paragraph("WORK SEARCH CONTACTS", ParagraphStyle('h', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor("#09090B"))))
    story.append(Paragraph("Illinois law requires a minimum of 3 work-search contacts per week.", sub_style))
    story.append(Spacer(1, 6))

    # Contact table - mirror Work Search Form columns
    header = ["#", "Date", "Employer Name & Address", "Method", "Position / Type of Work", "Result"]
    rows = [header]
    for i, c in enumerate(contacts, 1):
        emp = c.get("employer_name", "")
        addr = c.get("employer_address", "")
        emp_addr = f"{emp}\n{addr}" if addr else emp
        position = c.get("position_applied") or c.get("type_of_work","")
        if c.get("type_of_work") and c.get("position_applied"):
            position = f"{c['position_applied']}\n({c['type_of_work']})"
        rows.append([
            str(i),
            c.get("contact_date",""),
            Paragraph(emp_addr.replace("\n", "<br/>"), label_style),
            c.get("contact_method",""),
            Paragraph(str(position).replace("\n", "<br/>"), label_style),
            Paragraph(c.get("result",""), label_style),
        ])
    # Pad to 3 minimum
    while len(rows) - 1 < 3:
        rows.append([str(len(rows)), "", "", "", "", ""])

    t = Table(rows, colWidths=[0.3*inch, 0.9*inch, 2.4*inch, 0.85*inch, 1.85*inch, 1.2*inch], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0033A0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTSIZE', (0,1), (-1,-1), 8.5),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#09090B")),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#D4D4D8")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # Compliance summary
    n = len(contacts)
    status_color = colors.HexColor("#16A34A") if n >= 3 else colors.HexColor("#DC2626")
    summary = Paragraph(
        f"<b>Total Contacts:</b> {n} / 3 required &nbsp;&nbsp; <b>Certified:</b> {'YES' if w.get('certified') else 'NO'} &nbsp;&nbsp; <b>Status:</b> <font color='{status_color}'>{'COMPLIANT' if n>=3 else 'NON-COMPLIANT'}</font>",
        styles['Normal']
    )
    story.append(summary)
    if w.get("notes"):
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>Notes:</b> {w['notes']}", styles['Normal']))

    story.append(Spacer(1, 22))
    sig = Table([
        ["Claimant Signature:", "_______________________________", "Date:", "______________"],
    ], colWidths=[1.4*inch, 3.0*inch, 0.6*inch, 1.5*inch])
    sig.setStyle(TableStyle([('FONTSIZE', (0,0), (-1,-1), 9)]))
    story.append(sig)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by Illinois UI Tracker. "
        "This unofficial report mirrors the IDES Work Search form (ADJ034F).",
        sub_style
    ))

    doc.build(story)
    buf.seek(0)
    await log_audit(user["id"], "EXPORT_PDF", "benefit_week", wid, f"Generated report for week {w['week_start']}")
    return StreamingResponse(buf, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=BenefitWeek_{w['week_start']}.pdf"
    })


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
    recent = await db.benefit_weeks.find(week_q, {"_id": 0}).sort("week_start", -1).to_list(100)
    for w in recent:
        n = await db.contacts.count_documents({"benefit_week_id": w["id"]})
        if n >= 3:
            compliant += 1
        else:
            non_compliant += 1
    profile = None
    if cid:
        profile = await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    return {
        "total_weeks": weeks,
        "total_contacts": contacts,
        "compliant_weeks": compliant,
        "non_compliant_weeks": non_compliant,
        "profile_complete": bool(profile and profile.get("first_name") and profile.get("last_name")),
        "active_claimant_id": cid,
    }


# ============== CSV Export ==============
@api.get("/contacts/export.csv")
async def export_contacts_csv(week_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {"user_id": user["id"]}
    if week_id:
        q["benefit_week_id"] = week_id
    else:
        cid = await get_active_claimant_id(user["id"])
        if cid:
            q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    contacts = await db.contacts.find(q, {"_id": 0}).sort("contact_date", 1).to_list(10000)
    buf = io.StringIO()
    fields = ["contact_date", "employer_name", "employer_address", "contact_method",
              "position_applied", "type_of_work", "person_contacted", "result", "source_url"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for c in contacts:
        writer.writerow(c)
    buf.seek(0)
    await log_audit(user["id"], "EXPORT_CSV", "contact", week_id, f"Exported {len(contacts)} contacts to CSV")
    fname = f"contacts_{week_id or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# ============== Password Reset ==============
@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotPwIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if user:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.password_resets.insert_one({
            "token": token,
            "user_id": user["id"],
            "expires_at": expires,  # BSON datetime — TTL index will auto-clean
            "used": False,
            "created_at": datetime.now(timezone.utc),
        })
        link = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={token}"
        html = f"""
        <div style="font-family: 'IBM Plex Sans', Arial, sans-serif; max-width:560px; margin:auto; color:#09090B;">
          <div style="background:#0033A0; color:#fff; padding:18px 24px;">
            <h2 style="margin:0; font-family:'Chivo',Arial,sans-serif; font-weight:900; letter-spacing:-0.01em;">Illinois UI Job Search Tracker</h2>
          </div>
          <div style="border:1px solid #D4D4D8; border-top:none; padding:24px;">
            <p>You requested a password reset for your Illinois UI Job Search Tracker account.</p>
            <p><a href="{link}" style="display:inline-block; background:#0033A0; color:#fff; padding:12px 20px; text-decoration:none; font-weight:600;">Reset Password</a></p>
            <p style="font-size:12px; color:#52525B;">This link expires in 1 hour. If you didn't request this, ignore this email.</p>
            <p style="font-size:12px; color:#52525B; word-break:break-all;">{link}</p>
          </div>
        </div>
        """
        sent = await send_email(email, "Reset your Illinois UI Tracker password", html)
        await log_audit(user["id"], "FORGOT_PW", "user", user["id"], f"Reset link sent (resend={'ok' if sent else 'fail'})")
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
    await db.users.update_one({"id": rec["user_id"]}, {"$set": {"password_hash": hash_password(body.password)}})
    await db.password_resets.update_one({"token": body.token}, {"$set": {"used": True}})
    await log_audit(rec["user_id"], "RESET_PW", "user", rec["user_id"], "Password reset via email link")
    return {"ok": True}


# ============== Admin (case-worker) ==============
async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@api.get("/admin/users")
async def admin_list_users(admin=Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
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
    weeks = await db.benefit_weeks.find({"user_id": uid}, {"_id": 0}).sort("week_start", -1).to_list(500)
    for w in weeks:
        w["contact_count"] = await db.contacts.count_documents({"benefit_week_id": w["id"]})
    return {"user": user, "claimants": claimants, "weeks": weeks}


# ============== Reminders ==============
def _reminder_html(title: str, body_html: str) -> str:
    return f"""
    <div style="font-family:'IBM Plex Sans',Arial,sans-serif; max-width:560px; margin:auto; color:#09090B;">
      <div style="background:#0033A0; color:#fff; padding:16px 24px;">
        <h2 style="margin:0; font-family:'Chivo',Arial,sans-serif; font-weight:900; letter-spacing:-0.01em;">{title}</h2>
      </div>
      <div style="border:1px solid #D4D4D8; border-top:none; padding:24px;">{body_html}
        <p style="font-size:12px; color:#52525B; margin-top:24px;">
          Illinois law requires a minimum of 3 work-search contacts per benefit week (Sunday–Saturday).
          You can disable reminders from your Claimant profile.
        </p>
      </div>
    </div>
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
    # iterate claimants that have reminders_enabled
    claimants = await db.profiles.find({"user_id": user["id"], "reminders_enabled": {"$ne": False}}, {"_id": 0}).to_list(50)
    if not claimants:
        return 0
    sun, sat = _current_week_bounds()
    sent = 0
    for c in claimants:
        # Find this week's matching benefit week
        w = await db.benefit_weeks.find_one({"user_id": user["id"], "claimant_id": c["id"], "week_start": sun, "week_end": sat}, {"_id": 0})
        contacts_count = 0
        contacts_list = []
        if w:
            contacts_list = await db.contacts.find({"benefit_week_id": w["id"]}, {"_id": 0}).to_list(50)
            contacts_count = len(contacts_list)

        to_email = c.get("reminder_email") or user.get("email")
        name = f"{c.get('first_name','')} {c.get('last_name','')}".strip() or c.get("label", "claimant")
        deficit = max(0, 3 - contacts_count)

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
            list_html = "".join(f"<li>{x.get('contact_date','')} — {x.get('employer_name','')} ({x.get('position_applied','') or x.get('type_of_work','')})</li>" for x in contacts_list)
            body = f"<p>Hi {name}, you have <b>{contacts_count} / 3</b> contacts for {sun} → {sat}.</p>" + (f"<ul>{list_html}</ul>" if list_html else "")
            if contacts_count < 3:
                body += f"<p style='color:#DC2626; font-weight:600;'>Log {deficit} more before Saturday end-of-day to stay compliant.</p>"
        elif kind == "saturday":
            title = "End-of-Week Summary"
            status_txt = "✅ Compliant" if contacts_count >= 3 else "⚠️ Non-compliant"
            list_html = "".join(f"<li>{x.get('contact_date','')} — {x.get('employer_name','')}</li>" for x in contacts_list)
            body = f"<p>Hi {name}, here's your summary for {sun} → {sat}:</p><p><b>{contacts_count} contacts logged</b> — {status_txt}</p>" + (f"<ul>{list_html}</ul>" if list_html else "")
        else:
            return 0

        html = _reminder_html(title, body)
        ok = await send_email(to_email, title, html)
        if ok:
            sent += 1
            await log_audit(user["id"], f"REMINDER_{kind.upper()}", "claimant", c["id"], f"Email sent to {to_email}")

        # SMS reminder (optional + rate-limited + only if phone is verified)
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


@api.post("/reminders/test")
async def reminder_test(kind: str = "friday", user=Depends(get_current_user)):
    if kind not in ("sunday", "wednesday", "friday", "saturday"):
        raise HTTPException(status_code=400, detail="kind must be sunday|wednesday|friday|saturday")
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
    recent = await db.benefit_weeks.find(q, {"_id": 0}).sort("week_start", -1).to_list(min(max(weeks, 1), 52))
    recent.reverse()
    out = []
    for w in recent:
        n = await db.contacts.count_documents({"benefit_week_id": w["id"]})
        out.append({
            "week_start": w["week_start"],
            "week_end": w["week_end"],
            "contacts": n,
            "target": 3,
            "compliant": n >= 3,
        })
    return out


# ============== Invite Codes (Admin) ==============
@api.post("/admin/invites")
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
    # Send email
    html = f"""
    <div style="font-family:'IBM Plex Sans',Arial,sans-serif; max-width:560px; margin:auto; color:#09090B;">
      <div style="background:#0033A0; color:#fff; padding:18px 24px;">
        <h2 style="margin:0; font-family:'Chivo',Arial,sans-serif; font-weight:900;">You're invited</h2>
      </div>
      <div style="border:1px solid #D4D4D8; border-top:none; padding:24px;">
        <p>A case worker has invited you to the Illinois UI Job Search Tracker.</p>
        {f'<p style="background:#F4F4F5; padding:12px; border-left:3px solid #0033A0;">{body.note}</p>' if body.note else ''}
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
        it["invite_link"] = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{it['code']}"
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
    return {"email": inv["email"], "claimant_label": inv.get("claimant_label", "Primary"), "note": inv.get("note", "")}


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
        "claimant_id_last4": "",
        "address": "", "city": "", "state": "IL", "zip_code": "",
        "phone": "", "occupation": "",
        "reminders_enabled": True,
        "reminder_email": "",
        "sms_enabled": False,
        "sms_phone": "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.users.update_one({"id": uid}, {"$set": {"active_claimant_id": pid}})
    await db.invites.update_one({"code": body.code}, {"$set": {"used": True, "used_at": datetime.now(timezone.utc), "redeemed_user_id": uid}})
    await log_audit(uid, "REGISTER_INVITE", "user", uid, f"Invited account created from {inv.get('created_by')}")
    token = create_token(uid, inv["email"])
    return {"token": token, "user": {"id": uid, "email": inv["email"], "name": body.name, "role": "user"}}


# ============== SMS Phone OTP Verification ==============
class OtpSendIn(BaseModel):
    claimant_id: str
    phone: str


class OtpVerifyIn(BaseModel):
    claimant_id: str
    code: str


@api.post("/sms/send-otp")
async def sms_send_otp(body: OtpSendIn, user=Depends(get_current_user)):
    c = await db.profiles.find_one({"id": body.claimant_id, "user_id": user["id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Claimant not found")
    phone = body.phone.strip()
    if not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Phone must be E.164 (e.g. +13125550100)")
    # Generate 6-digit code
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
    msg = f"Illinois UI Tracker verification code: {code} (expires in 10 minutes)"
    sent, reason = await send_sms_rate_limited(phone, msg, body.claimant_id)
    await log_audit(user["id"], "OTP_SEND", "claimant", body.claimant_id, f"OTP to {phone}: {'sent' if sent else reason}")
    if not sent:
        raise HTTPException(status_code=502, detail=f"Could not send SMS ({reason}). Make sure the number is verified in Twilio for trial accounts.")
    return {"ok": True, "expires_in_minutes": 10}


@api.post("/sms/verify-otp")
async def sms_verify_otp(body: OtpVerifyIn, user=Depends(get_current_user)):
    rec = await db.otp_codes.find_one(
        {"claimant_id": body.claimant_id, "user_id": user["id"], "used": False},
        sort=[("created_at", -1)]
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
        {"$set": {"sms_verified": True, "sms_phone": rec["phone"], "sms_verified_at": datetime.now(timezone.utc).isoformat()}}
    )
    await log_audit(user["id"], "OTP_VERIFY", "claimant", body.claimant_id, f"Phone {rec['phone']} verified")
    return {"ok": True, "phone": rec["phone"]}


# ============== Mailgun Webhook ==============
@api.post("/webhooks/mailgun")
async def mailgun_webhook(request: Request):
    """Public webhook (no auth — Mailgun signs payloads but for simplicity we just log).
    Handles: email.bounced, email.complained, email.delivered."""
    payload = await request.json()
    event_type = payload.get("type", "")
    data = payload.get("data", {}) or {}
    to_emails = data.get("to") or []
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    await db.email_events.insert_one({
        "id": str(uuid.uuid4()),
        "type": event_type,
        "to": to_emails,
        "received_at": datetime.now(timezone.utc),
        "raw": data,
    })
    # Disable reminders for bounced / complained addresses
    if event_type in ("email.bounced", "email.complained"):
        for addr in to_emails:
            await db.profiles.update_many(
                {"reminder_email": addr},
                {"$set": {"reminders_enabled": False, "email_bounced": True, "email_bounced_at": datetime.now(timezone.utc).isoformat()}}
            )
            # Also disable when claimant has no override and the user's account email bounced
            users_with_email = await db.users.find({"email": addr.lower() if isinstance(addr, str) else ""}, {"_id": 0, "id": 1}).to_list(20)
            for u in users_with_email:
                await db.profiles.update_many(
                    {"user_id": u["id"], "reminder_email": ""},
                    {"$set": {"reminders_enabled": False, "email_bounced": True}}
                )
    return {"ok": True}


@api.get("/admin/email-events")
async def admin_email_events(admin=Depends(require_admin)):
    items = await db.email_events.find({}, {"_id": 0}).sort("received_at", -1).to_list(500)
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
        link = f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/invite/{code}"
        await send_email(
            email,
            "You're invited to Illinois UI Tracker",
            _reminder_html("You're invited", f"<p>A case worker invited you. <a href='{link}'>Accept invite</a></p><p style='font-size:11px; color:#52525B; word-break:break-all;'>{link}</p>"),
        )
        created.append({"email": email, "code": code, "invite_link": link})
    await log_audit(admin["id"], "INVITE_BULK", "invite", None, f"Created {len(created)}, skipped {len(skipped)}")
    return {"created": created, "skipped": skipped}


# ============== Integration Status (Admin) ==============
@api.get("/admin/integrations/status")
async def integrations_status(admin=Depends(require_admin)):
    has_mailgun = bool(os.environ.get("MAILGUN_API_KEY"))
    has_twilio = bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN") and os.environ.get("TWILIO_FROM_NUMBER"))
    domain = os.environ.get("MAILGUN_VERIFIED_DOMAIN", "")
    from_addr = os.environ.get("MAILGUN_FROM", "")
    return {
        "mailgun": {
            "configured": has_mailgun,
            "from": from_addr,
            "verified_domain": domain,
            "fallback_from": os.environ.get("MAILGUN_FALLBACK_FROM", "onboarding@mailgun.com"),
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

    # Seed demo user
    email = os.environ.get("ADMIN_EMAIL", "demo@illinoistracker.test").lower()
    password = os.environ.get("ADMIN_PASSWORD", "Demo1234!")
    existing = await db.users.find_one({"email": email})
    if not existing:
        uid = str(uuid.uuid4())
        await db.users.insert_one({
            "id": uid,
            "email": email,
            "name": "Demo Claimant",
            "password_hash": hash_password(password),
            "role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        pid = str(uuid.uuid4())
        await db.profiles.insert_one({
            "id": pid,
            "user_id": uid,
            "label": "Primary",
            "first_name": "Demo",
            "last_name": "Claimant",
            "middle_initial": "A",
            "claimant_id_last4": "1234",
            "address": "100 W Randolph St",
            "city": "Chicago",
            "state": "IL",
            "zip_code": "60601",
            "phone": "312-555-0100",
            "occupation": "Software Developer",
            "reminders_enabled": True,
            "reminder_email": "kmgagen@gmail.com",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await db.users.update_one({"id": uid}, {"$set": {"active_claimant_id": pid}})
    else:
        # keep password in sync with env if .env changed
        if not verify_password(password, existing["password_hash"]):
            await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})

    # Seed admin (case-worker) account
    admin_email = "admin@illinoistracker.app"
    admin_pw = "Admin1234!"
    if not await db.users.find_one({"email": admin_email}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "Admin / Case Worker",
            "password_hash": hash_password(admin_pw),
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Data migration: backfill claimant_id and active_claimant_id
    async for u in db.users.find({}, {"_id": 0, "id": 1, "active_claimant_id": 1, "role": 1}):
        if u.get("role") == "admin":
            continue
        active = u.get("active_claimant_id")
        if not active:
            p = await db.profiles.find_one({"user_id": u["id"]}, {"_id": 0, "id": 1})
            if p:
                active = p["id"]
                await db.users.update_one({"id": u["id"]}, {"$set": {"active_claimant_id": active}})
        if active:
            await db.benefit_weeks.update_many(
                {"user_id": u["id"], "claimant_id": {"$exists": False}},
                {"$set": {"claimant_id": active}}
            )
            await db.contacts.update_many(
                {"user_id": u["id"], "claimant_id": {"$exists": False}},
                {"$set": {"claimant_id": active}}
            )

    # Reminder scheduler
    if os.environ.get("MAILGUN_API_KEY"):
        try:
            scheduler = AsyncIOScheduler(timezone=pytz.timezone("America/Chicago"))
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="sun", hour=9, minute=0), args=["sunday"], id="rem_sun")
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="wed", hour=9, minute=0), args=["wednesday"], id="rem_wed")
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="fri", hour=9, minute=0), args=["friday"], id="rem_fri")
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="sat", hour=9, minute=0), args=["saturday"], id="rem_sat")
            scheduler.start()
            logging.info("Reminder scheduler started (America/Chicago)")
        except Exception as e:
            logging.warning(f"Could not start reminder scheduler: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    global scheduler
    if scheduler:
        try: scheduler.shutdown(wait=False)
        except Exception: pass
    client.close()


app.include_router(api)

# CORS - allow_origins must be explicit when allow_credentials=True
origins_env = os.environ.get('CORS_ORIGINS', '*')
allow_credentials = True
if origins_env.strip() == '*':
    allow_origins = ['*']
    allow_credentials = False
else:
    allow_origins = [o.strip() for o in origins_env.split(',') if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_credentials,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
