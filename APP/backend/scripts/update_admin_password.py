#!/usr/bin/env python3
"""Obsolete — admin passwords are no longer stored by this application.

Clerk owns credentials. This script used to write a bcrypt hash into
db.users.password_hash, which nothing reads any more, so running it would
silently do nothing useful.

To change an admin's password:
    Clerk dashboard -> Users -> select the user -> Reset password

To grant someone admin:
    add their email to the ADMIN_EMAILS environment variable; the role is
    applied on their next sign-in (see clerk_auth.get_or_create_user).
"""

raise SystemExit(__doc__)
