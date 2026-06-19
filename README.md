# Illinois UI Job Tracker

Illinois UI Job Tracker is a full-stack app designed to help people manage their unemployment insurance work-search contacts and job applications. It includes a FastAPI backend, a React/Tailwind frontend, and MongoDB storage.

## Overview

This project supports:
- authenticated caseworkers and claimants
- claimant profiles and active claimant selection
- benefit week tracking
- work-search contact logging
- CSV import/export of contacts
- screenshot text extraction via AI vision
- PDF report generation for benefit-week forms
- email reminders and SMS notifications
- admin invite and audit tooling

## Architecture

- Backend: `APP/backend/server.py`
  - FastAPI + Motor (async MongoDB)
  - JWT auth and role-based admin protection
  - Mailgun and Twilio integration points
  - APScheduler-driven reminder scheduler
- Frontend: `APP/frontend`
  - React application with Tailwind UI
  - Pages for login, dashboard, claimants, weeks, and more
- Database: MongoDB
  - collections include `users`, `profiles`, `benefit_weeks`, `contacts`, `invites`, `audit_log`, and more

## Prerequisites

- Python 3.11+
- Node.js 18+
- Yarn
- MongoDB

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/cagedbear83/job-tracker.git
cd job-tracker
```

### 2. Backend setup

```bash
cd APP/backend
python -m venv .venv
.venv\Scripts\activate    # Windows
# or
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
# For running the test suite, also: pip install -r requirements-dev.txt
# Ensure the correct JWT package is installed (PyJWT), not the unrelated jwt package.
```

### 3. Frontend setup

```bash
cd APP/frontend
yarn install
```

## Environment variables

Create a `.env` file in `APP/backend` with the following values.

### Required for backend startup

```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="ides_tracker_db"
JWT_SECRET="<strong-random-secret>"
FRONTEND_URL="http://localhost:3000"
```

### Optional integrations

```env
MAILGUN_API_KEY="<your-mailgun-api-key>"
MAILGUN_DOMAIN="<your-mailgun-domain>"
MAILGUN_FROM="Illinois UI Tracker <noreply@yourdomain.com>"
TWILIO_ACCOUNT_SID="<your-twilio-sid>"
TWILIO_AUTH_TOKEN="<your-twilio-auth-token>"
TWILIO_FROM_NUMBER="+12345678900"
```

### Production hardening (all optional)

```env
# Error tracking — leave blank to disable Sentry
SENTRY_DSN=""
SENTRY_ENVIRONMENT="production"
# Per-IP auth rate limits (set RATE_LIMIT_ENABLED=false for integration tests)
RATE_LIMIT_ENABLED="true"
RATE_LIMIT_STORAGE_URI=""   # e.g. redis://... to share limits across workers
# Send HSTS header (only behind TLS)
ENABLE_HSTS="true"
```

### Development helper flags

```env
ENABLE_DEMO_USER="true"
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
```

> Security notes
> - `JWT_SECRET` is required and has no fallback in production.
> - `ADMIN_EMAIL` / `ADMIN_PASSWORD` are only created when explicitly configured.
> - Demo seeding is disabled unless `ENABLE_DEMO_USER=true`.

## Local development .env example

```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="ides_tracker_db"
JWT_SECRET="dev-secret-change-me"
FRONTEND_URL="http://localhost:3000"
MAILGUN_API_KEY=""
MAILGUN_DOMAIN=""
MAILGUN_FROM=""
TWILIO_ACCOUNT_SID=""
TWILIO_AUTH_TOKEN=""
TWILIO_FROM_NUMBER=""
ENABLE_DEMO_USER="true"
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
```

## Running the app

### Backend

```bash
cd APP/backend
.venv\Scripts\activate    # Windows
uvicorn server:app --reload --port 8001
```

### Frontend

```bash
cd APP/frontend
yarn start
```

## Deployment

For production, run the backend without `--reload` and point it at a production MongoDB instance.

```bash
cd APP/backend
.venv\Scripts\activate    # Windows
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
```

> Use a single worker for now: the reminder scheduler (APScheduler) runs
> in-process, so multiple workers would fire each cron job more than once.
> Splitting the scheduler into its own worker is a planned follow-up.

Set `CORS_ORIGINS` explicitly in `APP/backend/.env` for your frontend domain:

```env
CORS_ORIGINS="https://yourdomain.com"
```

### Docker (local full stack)

```bash
docker compose up --build
```

This starts MongoDB and the backend (on `:8001`). Run the React frontend
separately with `yarn start`, or deploy it to Vercel.

### Health checks

The backend exposes probes for load balancers / uptime monitors (outside the
`/api` prefix):

- `GET /health/live` — process is up
- `GET /health/ready` — dependencies reachable (pings MongoDB; `503` if not)

### Hosted deploy

- **Frontend → Vercel:** set the project root to `APP/frontend`; `vercel.json`
  handles the SPA rewrite, security headers, and asset caching. Set
  `REACT_APP_BACKEND_URL` (and optional `REACT_APP_SENTRY_DSN`) in the project.
- **Backend → Render:** `render.yaml` is a Docker Blueprint with a
  `/health/ready` health check. Provide `MONGO_URL` (e.g. MongoDB Atlas),
  `FRONTEND_URL`, and `CORS_ORIGINS` as secrets.

For email and SMS in production, configure:
- `MAILGUN_API_KEY`
- `MAILGUN_DOMAIN`
- `MAILGUN_FROM`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`

Protect your production secret values and never commit `.env` to source control.

## Running tests

### Backend tests

```bash
cd APP/backend
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

> The Round 3/4 suites are integration tests that hit a running backend. Start
> that backend with `RATE_LIMIT_ENABLED=false` so repeated logins during the
> suite are not throttled by the new auth rate limits.

### Frontend tests

```bash
cd APP/frontend
yarn test
```

## Project structure

```text
job-tracker/
├── APP/
│   ├── backend/
│   │   ├── assets/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   ├── requirements-dev.txt
│   │   ├── server.py
│   │   └── .env
│   ├── frontend/
│   │   ├── public/
│   │   ├── src/
│   │   ├── package.json
│   │   └── README.md
│   └── memory/
├── design_guidelines.json
├── requirements.txt
└── README.md
```

## Features

- User registration, login, and JWT authentication
- Claimant profile management
- Benefit week tracking and work-search contact logging
- CSV import/export for contacts
- Screenshot OCR import via AI vision
- PDF report generation for benefit-week reports
- Dashboard summaries and trend analytics
- Admin-only invite, user, and integration management
- Mailgun webhook processing with signature verification

## Notes

- The backend includes an admin guard for `/api/admin/*` routes.
- Mailgun webhook requests are verified before updating reminder settings.
- CORS origins are configurable via `CORS_ORIGINS` in `APP/backend/.env`.

## License

This project is available under the MIT License.

Add screenshots or a short demo GIF here once the interface is ready.

```md
![Dashboard screenshot](path/to/screenshot.png)
```

## Roadmap

- Add authentication.
- Add filtering and search.
- Add dashboard analytics.
- Add reminders for follow-ups.
- Add export/import support.

## Contributing

Contributions, ideas, and improvements are welcome. Open an issue to discuss changes or submit a pull request when the contribution workflow is ready.

## License

MIT License

Copyright (c) 2026 Kyle Gagen

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

