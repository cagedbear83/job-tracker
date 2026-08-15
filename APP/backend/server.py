# Composition root — wires the split routers onto the app.
# Foundation (app, api, db, models, helpers) lives in core.py;
# route handlers live in routers/*.py.
from core import *  # noqa: F401,F403 — re-exports app, api, os, CORSMiddleware, helpers
from core import app, api
from core import _broadcast_reminders, _purge_due_accounts
from routers import account, admin, audit, auth, billing_routes, calendar, contact, contacts, dashboard, documents, imports, invites, misc, profile, reminders, reports, sms, webhooks, weeks

# Attach every domain router onto the /api router before mounting it.
for _r in (account.router, admin.router, audit.router, auth.router, billing_routes.router, calendar.router, contact.router, contacts.router, dashboard.router, documents.router, imports.router, invites.router, misc.router, profile.router, reminders.router, reports.router, sms.router, webhooks.router, weeks.router):
    api.include_router(_r)



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
    await db.subscriptions.create_index("user_id", unique=True)
    await db.subscriptions.create_index("stripe_customer_id")
    await db.subscriptions.create_index("stripe_subscription_id")
    await db.usage_counters.create_index(
        [("user_id", 1), ("feature", 1), ("period", 1)], unique=True
    )
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

    # One-time migration: earlier registration code wrote profile docs with
    # ad-hoc keys (full_name / zip / is_primary) that the rest of the app never
    # reads, so those users' details didn't show on their profile. Rewrite any
    # such legacy docs into the canonical ProfileIn schema. Idempotent: matches
    # only docs that still have a legacy key.
    try:
        legacy_migrated = 0
        async for p in db.profiles.find(
            {"$or": [
                {"full_name": {"$exists": True}},
                {"zip": {"$exists": True}},
                {"is_primary": {"$exists": True}},
            ]}
        ):
            full_name = (p.get("full_name") or "").strip()
            first = p.get("first_name")
            last = p.get("last_name")
            if not first and not last and full_name:
                parts = full_name.split(None, 1)
                first = parts[0]
                last = parts[1] if len(parts) > 1 else ""
            set_fields = {
                "label": p.get("label") or "Primary",
                "first_name": first or "",
                "last_name": last or "",
                "middle_initial": p.get("middle_initial", ""),
                "state": p.get("state") or "IL",
                "zip_code": p.get("zip_code") or p.get("zip", ""),
                "occupation": p.get("occupation", ""),
                "reminders_enabled": p.get("reminders_enabled", True),
                "reminder_email": p.get("reminder_email", ""),
                "sms_enabled": p.get("sms_enabled", False),
            }
            await db.profiles.update_one(
                {"id": p["id"]},
                {
                    "$set": set_fields,
                    "$unset": {"full_name": "", "zip": "", "is_primary": ""},
                },
            )
            legacy_migrated += 1
        if legacy_migrated:
            logging.info(f"Migrated {legacy_migrated} legacy profile(s) to canonical schema")
    except Exception as e:
        logging.warning(f"Legacy profile migration skipped: {e}")

    demo_user_enabled = os.environ.get("ENABLE_DEMO_USER", "true").lower() in ("1", "true", "yes")
    demo_email = os.environ.get("DEMO_USER_EMAIL", "demo@illinoistracker.test").lower()
    demo_password = os.environ.get("DEMO_USER_PASSWORD", "Demo1234!")
    if demo_user_enabled:
        existing = await db.users.find_one({"email": demo_email})
        if not existing:
            uid = str(uuid.uuid4())
            await db.users.insert_one({
                "id": uid,
                "email": demo_email,
                "name": "Demo Claimant",
                "password_hash": hash_password(demo_password),
                "role": "user",
                "email_verified": True,
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
            })
            await db.users.update_one({"id": uid}, {"$set": {"active_claimant_id": pid}})
        else:
            update = {"email_verified": True}
            if not verify_password(demo_password, existing["password_hash"]):
                update["password_hash"] = hash_password(demo_password)
            await db.users.update_one({"email": demo_email}, {"$set": update})
    else:
        logging.info("Demo user seeding disabled. Set ENABLE_DEMO_USER=true to enable it.")

    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_pw = os.environ.get("ADMIN_PASSWORD", "")
    if admin_email and admin_pw:
        existing_admin = await db.users.find_one({"email": admin_email})
        if not existing_admin:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": admin_email,
                "name": "Admin / Case Worker",
                "password_hash": hash_password(admin_pw),
                "role": "admin",
                "email_verified": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        elif existing_admin.get("role") == "admin" and not verify_password(admin_pw, existing_admin["password_hash"]):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_password(admin_pw)}},
            )
        elif existing_admin.get("role") != "admin":
            logging.warning(f"Configured ADMIN_EMAIL {admin_email} already exists as non-admin. Skipping admin seed.")
    else:
        logging.warning("ADMIN_EMAIL and ADMIN_PASSWORD are not configured; no admin account will be created automatically.")

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
                {"$set": {"claimant_id": active}},
            )
            await db.contacts.update_many(
                {"user_id": u["id"], "claimant_id": {"$exists": False}},
                {"$set": {"claimant_id": active}},
            )

    # The scheduler always runs (it hosts the account-purge job); reminder jobs
    # are only added when Mailgun is configured.
    try:
        scheduler = AsyncIOScheduler(timezone=pytz.timezone("America/Chicago"))
        # Daily hard-purge of soft-deleted accounts past their grace window.
        scheduler.add_job(
            _purge_due_accounts, CronTrigger(hour=3, minute=30), id="purge_accounts"
        )
        if os.environ.get("MAILGUN_API_KEY"):
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="sun", hour=9, minute=0), args=["sunday"], id="rem_sun")
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="wed", hour=9, minute=0), args=["wednesday"], id="rem_wed")
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="fri", hour=9, minute=0), args=["friday"], id="rem_fri")
            scheduler.add_job(_broadcast_reminders, CronTrigger(day_of_week="sat", hour=9, minute=0), args=["saturday"], id="rem_sat")
        scheduler.start()
        logging.info("Scheduler started (America/Chicago) — purge job active")
    except Exception as e:
        logging.warning(f"Could not start scheduler: {e}")


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
        return JSONResponse(status_code=503, content={"status": "not ready", "mongo": "error"})


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_credentials,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Security headers ==============
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if os.environ.get("ENABLE_HSTS", "false").lower() in ("1", "true", "yes"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    return response
