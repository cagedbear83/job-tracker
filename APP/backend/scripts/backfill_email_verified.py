#!/usr/bin/env python3
"""One-off backfill for users.email_verified on Clerk-provisioned accounts.

Why this exists
    Every reminder sender in core.py (_send_user_reminder and both calendar
    reminder jobs) skips users whose `email_verified` is falsy. Before the
    Clerk migration the old /auth/verify-email endpoint set it. After the
    migration nothing did, so accounts created through Clerk never received
    weekly, 3-day, or 5PM certification reminders.

    clerk_auth.get_or_create_user now records the flag on provisioning and
    heals it on a user's next authenticated request. This script covers the
    users who will not sign in before their next reminder is due, which is
    exactly the people the reminders are for.

What it touches
    Only users that have a `clerk_id` and whose `email_verified` is not
    already True. Pre-migration users who never signed in through Clerk have
    no clerk_id and keep the flag the old flow gave them.

    Sets `email_verified` (True/False, from Clerk) and
    `email_verified_checked_at` (UTC ISO timestamp). Nothing else.

Usage (from APP/backend, with the production env loaded)
    python scripts/backfill_email_verified.py            # dry run, changes nothing
    python scripts/backfill_email_verified.py --apply    # write the changes

Required env: MONGO_URL, DB_NAME, CLERK_SECRET_KEY
Optional env: CLERK_API_BASE (default https://api.clerk.com/v1)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import requests
from pymongo import MongoClient

# Clerk's Backend API allows 100 requests per 10 seconds per instance.
# 0.15s between calls stays well under that and leaves headroom for the
# running app, which shares the same limit.
REQUEST_SPACING_SECONDS = 0.15


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        sys.exit(f"Missing required environment variable: {name}")
    return value


def _primary_verified(clerk_user: dict) -> bool:
    """Same rule as clerk_auth._primary_email_verified, kept standalone so
    this script does not import clerk_auth (which needs CLERK_ISSUER and
    fetches the JWKS at import time)."""
    addrs = clerk_user.get("email_addresses") or []
    primary_id = clerk_user.get("primary_email_address_id")
    addr = next((a for a in addrs if a.get("id") == primary_id), None)
    if addr is None:
        addr = addrs[0] if addrs else {}
    return ((addr.get("verification") or {}).get("status")) == "verified"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--limit", type=int, default=0, help="stop after N users (0 = all)")
    args = parser.parse_args()

    db = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
    secret = _env("CLERK_SECRET_KEY")
    api_base = os.environ.get("CLERK_API_BASE", "https://api.clerk.com/v1").rstrip("/")
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {secret}"

    query = {"clerk_id": {"$exists": True, "$ne": None}, "email_verified": {"$ne": True}}
    total = db.users.count_documents(query)
    print(f"{'APPLY' if args.apply else 'DRY RUN'}: {total} Clerk user(s) without email_verified=True")

    counts = {"verified": 0, "unverified": 0, "missing_in_clerk": 0, "errors": 0}
    cursor = db.users.find(query, {"_id": 0, "id": 1, "email": 1, "clerk_id": 1})
    if args.limit:
        cursor = cursor.limit(args.limit)

    for user in cursor:
        try:
            resp = session.get(f"{api_base}/users/{user['clerk_id']}", timeout=15)
        except requests.RequestException as e:
            counts["errors"] += 1
            print(f"  ERROR    {user['email']}: {e}")
            continue
        finally:
            time.sleep(REQUEST_SPACING_SECONDS)

        if resp.status_code == 404:
            counts["missing_in_clerk"] += 1
            print(f"  MISSING  {user['email']} (clerk_id {user['clerk_id']} not found in Clerk)")
            continue
        if resp.status_code != 200:
            counts["errors"] += 1
            print(f"  ERROR    {user['email']}: Clerk returned HTTP {resp.status_code}")
            continue

        verified = _primary_verified(resp.json())
        counts["verified" if verified else "unverified"] += 1
        print(f"  {'VERIFIED' if verified else 'UNVERIF.'} {user['email']}")

        if args.apply:
            db.users.update_one(
                {"id": user["id"]},
                {"$set": {
                    "email_verified": verified,
                    "email_verified_checked_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

    print(
        f"\nverified={counts['verified']} unverified={counts['unverified']} "
        f"missing_in_clerk={counts['missing_in_clerk']} errors={counts['errors']}"
    )
    if not args.apply:
        print("Dry run: nothing was written. Re-run with --apply to save.")
    return 1 if counts["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
