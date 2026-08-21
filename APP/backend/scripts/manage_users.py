#!/usr/bin/env python3
"""Admin utilities for user management (listing only).

Password reset moved to Clerk — see reset_password() below.

Usage examples:
  python manage_users.py --list
  python manage_users.py --email user@example.com --generate --dry-run
  python manage_users.py --email user@example.com --password NewPass123! --apply
"""
import argparse
import os
import secrets
# bcrypt import removed — the hashing path below is unreachable (see reset_password)
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'ides_tracker_db')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def list_users(limit: int = 50):
    for u in db.users.find({}, {'_id': 0, 'id': 1, 'email': 1, 'role': 1}).limit(limit):
        print(u)


def reset_password(email: str, new_password: str | None = None, generate: bool = False, apply: bool = False):
    raise SystemExit(
        "Password reset is no longer handled here. Clerk owns credentials, "
        "so this app stores no password hash and writing one to Mongo would "
        "change nothing. Reset it from the Clerk dashboard (Users -> select "
        "user -> Reset password), or have the user click Forgot password in "
        "the app. Note that --list still works."
    )
    if not new_password and not generate:
        raise ValueError('Either provide --password or --generate')
    if generate:
        new_password = secrets.token_urlsafe(12)
    user = db.users.find_one({'email': email})
    if not user:
        print('User not found:', email)
        return 2
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    print(f"User: {email}")
    print('New password (plaintext):', new_password)
    print('Password hash preview:', hashed[:20] + '...')
    if apply:
        res = db.users.update_one({'email': email}, {'$set': {'password_hash': hashed, 'updated_at': datetime.utcnow().isoformat()}})
        if res.matched_count:
            print('Password updated in DB')
            return 0
        else:
            print('DB update failed')
            return 3
    else:
        print('Dry-run: not applying changes. Use --apply to persist.')
        return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--list', action='store_true', help='List users')
    p.add_argument('--email', help='User email to act on')
    p.add_argument('--password', help='New password to set')
    p.add_argument('--generate', action='store_true', help='Generate a secure random password')
    p.add_argument('--apply', action='store_true', help='Apply changes to the database (otherwise dry-run)')
    p.add_argument('--limit', type=int, default=50, help='Limit for listing users')
    args = p.parse_args()

    if args.list:
        list_users(args.limit)
        return
    if args.email:
        try:
            code = reset_password(args.email, args.password, args.generate, args.apply)
            raise SystemExit(code)
        except Exception as e:
            print('Error:', e)
            raise
    p.print_help()


if __name__ == '__main__':
    main()
