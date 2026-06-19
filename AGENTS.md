# AGENTS.md

## Cursor Cloud specific instructions

This is a full-stack app (see `README.md` for the product overview and standard
commands). Three services are involved:

| Service  | Dir              | Dev command (run from the dir)                                  | Port  |
| -------- | ---------------- | -------------------------------------------------------------- | ----- |
| MongoDB  | —                | `mongod --dbpath /data/db --bind_ip 127.0.0.1 --port 27017`   | 27017 |
| Backend  | `APP/backend`    | `. .venv/bin/activate && uvicorn server:app --reload --port 8001` | 8001  |
| Frontend | `APP/frontend`   | `PORT=3000 BROWSER=none yarn start`                            | 3000  |

The dependency-refresh layer (Python venv + pip, yarn) is handled by the
startup update script. The notes below are the non-obvious caveats needed to
actually run/test the app.

### MongoDB
- Installed via apt (`mongodb-org`), but there is **no systemd** in this VM, so
  it will not auto-start. Start it manually with the command above (data dir
  `/data/db` already exists and is owned by the `ubuntu` user). Verify with
  `mongosh --quiet --eval 'db.runCommand({ping:1})'`.

### Environment files (gitignored, not in the repo)
- Both services need a `.env`. Create them once with
  `cp APP/backend/.env.example APP/backend/.env` and
  `cp APP/frontend/.env.example APP/frontend/.env`.
- The backend `.env` is configured to seed the accounts the integration tests
  expect: `DEMO_USER_EMAIL=demo@illinoistracker.app` / `Demo1234!` and
  `ADMIN_EMAIL=admin@illinoistracker.app` / `Admin1234!`.

### Login requires verified email — verify seeded accounts before logging in
- `/api/auth/login` rejects any user whose `email_verified` is not `true`.
- The startup seeder creates the demo/admin users **unverified**, and with no
  Mailgun configured (default in dev) **no verification email is sent**, so you
  cannot log in until you flip the flag directly in Mongo:
  ```
  mongosh "mongodb://localhost:27017/ides_tracker_db" --quiet --eval \
    'db.users.updateMany({email:{$in:["demo@illinoistracker.app","admin@illinoistracker.app"]}},{$set:{email_verified:true}})'
  ```
  Re-run this any time the DB is wiped/reseeded (a fresh `/data/db`). The same
  applies to any account created through the Register flow in dev.

### Tests
- Backend tests (`APP/backend/tests/`) are **integration** tests that hit a
  live server. The backend must be running, and you must export
  `REACT_APP_BACKEND_URL=http://localhost:8001` before running pytest:
  `REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest tests/ -q`.
- A handful of tests are expected to fail in this environment and are not setup
  problems: two reference the original container path `/app/backend/...`
  (`test_ides_logo_file_exists`, the PDF logo check), and the Mailgun/Twilio
  tests require those optional integrations to be configured
  (`test_integrations_status_admin`, `test_admin_email_events_list`,
  `test_reminder_friday_send_one`, `test_sms_code_path_via_friday_reminder`).
- Frontend has **no standalone lint script**; ESLint runs as part of the CRACO
  webpack build, so `yarn start`/`yarn build` compiling cleanly means lint
  passed.
