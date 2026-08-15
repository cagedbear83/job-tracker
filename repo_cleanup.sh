#!/usr/bin/env bash
# Repo hygiene cleanup for the job-tracker repo.
# Run from the repo root:  bash repo_cleanup.sh
# Safe to re-run. Uses `git rm --cached --ignore-unmatch` so it won't error on
# files that aren't tracked; it then deletes the on-disk copies.
set -u

echo "== 1. Confirm no real .env is tracked (should print NOTHING) =="
git ls-files | grep -E '(^|/)\.env$|\.env\.' | grep -v '\.env\.example' || echo "  OK: no .env tracked"

echo
echo "== 2. Remove committed backups / archives / OS cruft =="
git rm --cached --ignore-unmatch \
  "APP/backend/server_monolith_backup.py.bak" \
  "APP/backend/files.zip" \
  ".DS_Store" "APP/.DS_Store" 2>/dev/null
rm -f "APP/backend/server_monolith_backup.py.bak" "APP/backend/files.zip" \
      ".DS_Store" "APP/.DS_Store" 2>/dev/null

echo
echo "== 3. Remove ad-hoc debug/scratch scripts from APP/backend =="
cd APP/backend 2>/dev/null || { echo "run me from the repo root"; exit 1; }
for f in call_login_direct.py check_login_verify.py check_users.py \
         inspect_jwt.py login_test.py simulate_login.py \
         test_jwt_encode.py test_jwt_encode2.py "Test Email.py" verify_routes.py; do
  git rm --cached --ignore-unmatch "$f" 2>/dev/null
  rm -f "$f" 2>/dev/null
done
cd - >/dev/null

echo
echo "== 4. (Optional) keep real ops scripts but move them out of the app root =="
echo "   These look like legitimate maintenance tools — review, then relocate:"
echo "     APP/backend/manage_users.py"
echo "     APP/backend/update_admin_password.py"
echo "   e.g.:  mkdir -p APP/backend/scripts && git mv APP/backend/manage_users.py APP/backend/scripts/"

echo
echo "== 5. Stop tracking caches if any slipped in =="
git rm -r --cached --ignore-unmatch \
  "APP/.ruff_cache" "**/__pycache__" 2>/dev/null

echo
echo "== Done. Review with:  git status   then commit. =="