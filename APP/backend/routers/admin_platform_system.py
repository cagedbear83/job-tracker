# Ported from admin_portal/admin_system.py.
#
# Admin platform: System health module.
#
# Surfaces the health of the app's external dependencies for staff +
# platform_admin. Does NOT re-implement Sentry — it links to the existing
# Sentry project (core.py already wires SENTRY_DSN) and reports which
# integrations are configured. Checks are best-effort and never throw.
#
# All the env var names below (MAILGUN_*, TWILIO_*, GEMINI_API_KEY,
# STRIPE_SECRET_KEY, SENTRY_DSN) already match this codebase's core.py /
# .env.example exactly — no renaming was needed.
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from core import db
from rbac import require_staff

router = APIRouter(prefix="/admin/platform/system", tags=["admin-platform:system"])


def _configured(*env_keys: str) -> bool:
    return all(os.environ.get(k) for k in env_keys)


@router.get("/health", dependencies=[Depends(require_staff)])
async def system_health():

    # MongoDB ping
    try:
        await db.command("ping")
        mongo_ok = True
        mongo_err = None
    except Exception as e:
        mongo_ok, mongo_err = False, str(e)

    checks = {
        "mongodb": {"ok": mongo_ok, "error": mongo_err},
        "mailgun": {"configured": _configured("MAILGUN_API_KEY", "MAILGUN_DOMAIN")},
        "twilio": {"configured": _configured("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN")},
        "gemini": {"configured": _configured("GEMINI_API_KEY")},
        "stripe": {
            "configured": bool(os.environ.get("STRIPE_SECRET_KEY")),
            "mode": ("test" if os.environ.get("STRIPE_SECRET_KEY", "").startswith("sk_test_")
                     else "live" if os.environ.get("STRIPE_SECRET_KEY") else None),
        },
        "sentry": {
            "configured": bool(os.environ.get("SENTRY_DSN")),
            "dashboard_url": os.environ.get("SENTRY_DASHBOARD_URL"),
        },
    }
    overall = mongo_ok and checks["stripe"]["configured"]
    return {
        "ok": overall,
        "checked_at": datetime.now(timezone.utc),
        "checks": checks,
    }
