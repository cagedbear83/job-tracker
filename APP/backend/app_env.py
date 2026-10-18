"""Which environment this process is running in.

Production is the default. Only an explicit APP_ENV of dev, development,
local or test turns the production-only safety checks off, so a deploy that
forgets to set APP_ENV gets the strict behavior rather than the loose one.

Production-only checks that read IS_PRODUCTION:
  - core.py:       refuses to boot when CORS_ORIGINS is unset or "*"
  - clerk_auth.py: refuses to boot when CLERK_AUTHORIZED_PARTIES is unset
  - server.py:     sends HSTS unless ENABLE_HSTS is explicitly false

Kept in its own module, with no imports from this app, so clerk_auth.py and
core.py can both read it without a circular import.
"""
import os

NON_PRODUCTION_ENVS = frozenset({"dev", "development", "local", "test"})

APP_ENV = (os.environ.get("APP_ENV") or "production").strip().lower()
IS_PRODUCTION = APP_ENV not in NON_PRODUCTION_ENVS
