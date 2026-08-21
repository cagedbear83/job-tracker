# Composition root — wires the split routers onto the app.
# Foundation (app, api, db, models, helpers) lives in core.py;
# route handlers live in routers/*.py.
from core import *  # noqa: F401,F403 — re-exports app, api, os, CORSMiddleware, helpers

import clerk_auth
from core import app, api
from core import _broadcast_reminders, _purge_due_accounts
from core import _broadcast_event_reminders, _send_certification_final_reminders
from routers import account, admin, audit, auth, billing_routes, calendar, contact, contacts, dashboard, documents, imports, invites, misc, profile, reminders, reports, sms, webhooks, weeks

# ---- Admin portal integration (ported from the standalone admin_portal
# module) — new admin-platform surface, namespaced under /api/admin/platform
# to avoid colliding with the existing /api/admin/* routes in routers/admin.py
# and routers/invites.py. See routers/admin_platform_compliance.py's module
# docstring for the full rationale.
from routers import (
    admin_platform_users,
    admin_platform_subscriptions,
    admin_platform_comps,
    admin_platform_refunds,
    admin_platform_system,
    admin_platform_compliance,
    admin_disputes,
)

# Attach every domain router onto the /api router before mounting it.
for _r in (account.router, admin.router, audit.router, auth.router, billing_routes.router, calendar.router, contact.router, contacts.router, dashboard.router, documents.router, imports.router, invites.router, misc.router, profile.router, reminders.router, reports.router, sms.router, webhooks.router, weeks.router,
           admin_platform_users.router, admin_platform_subscriptions.router, admin_platform_comps.router, admin_platform_refunds.router, admin_platform_system.router, admin_platform_compliance.router, admin_disputes.router):
    api.include_router(_r)



# ============== Startup ==============
scheduler: Optional[AsyncIOScheduler] = None


@app.on_event("startup")
async def on_startup():
    global scheduler

    # Prove Clerk is configured before serving a single request. A wrong
    # CLERK_ISSUER otherwise fails silently: the app boots fine and then 401s
    # every authenticated request, which looks like a broken login rather than
    # a bad environment variable. Fail here instead, naming the URL tried.
    clerk_config = clerk_auth.validate_config()
    logging.info(
        "Clerk OK — %s signing key(s) from %s; %s admin email(s) configured",
        clerk_config["key_count"],
        clerk_config["jwks_url"],
        clerk_config["admin_emails"],
    )
    if clerk_config["mismatch"]:
        logging.error("Clerk environment mismatch: %s", clerk_config["mismatch"])
    if not clerk_config["admin_emails"]:
        logging.warning(
            "ADMIN_EMAILS is empty — no account will be granted admin on sign-in."
        )

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
    # password_resets, refresh_tokens and invites are all retired collections —
    # Clerk owns password reset, session refresh, and invitations now, so none
    # of them is written any more and none needs indexing. Drop the collections
    # in Mongo whenever you feel like tidying; nothing reads them.

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

    # Account seeding moved to Clerk.
    #
    # This used to insert a demo user and an admin user into Mongo with bcrypt
    # password hashes from DEMO_USER_PASSWORD / ADMIN_PASSWORD. Under Clerk
    # those rows are unreachable — there is no local password check any more,
    # so an account that exists only in Mongo can never be signed in to.
    #
    # Admin access now works the other way round: create the account in Clerk
    # (or just sign up normally), and clerk_auth.get_or_create_user elevates it
    # on first sign-in if its email is listed in ADMIN_EMAILS. Authorization
    # still lives in this database — Clerk never decides who is an admin.
    if os.environ.get("ADMIN_PASSWORD") or os.environ.get("DEMO_USER_PASSWORD"):
        logging.warning(
            "ADMIN_PASSWORD / DEMO_USER_PASSWORD are set but no longer used — "
            "Clerk owns credentials. Set ADMIN_EMAILS instead and remove these."
        )
    if not os.environ.get("ADMIN_EMAILS"):
        logging.warning(
            "ADMIN_EMAILS is not configured; no account will be granted admin "
            "automatically. Set it to a comma-separated list of emails."
        )

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
            # Calendar event reminders (certification, IDES interview, appeal,
            # questionnaire, and the auto-added work-search follow-up). Daily
            # 8AM CT scan covers both the 3-days-ahead and morning-of cases;
            # certification gets its own 5PM CT email+SMS reminder instead of
            # the generic morning-of one, timed ahead of the 7PM CT IDES
            # filing cutoff. See core.py's "Calendar Event Reminders" section.
            scheduler.add_job(_broadcast_event_reminders, CronTrigger(hour=8, minute=0), args=["3day"], id="cal_3day")
            scheduler.add_job(_broadcast_event_reminders, CronTrigger(hour=8, minute=0), args=["morning"], id="cal_morning")
            scheduler.add_job(_send_certification_final_reminders, CronTrigger(hour=17, minute=0), id="cal_cert_5pm")
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
