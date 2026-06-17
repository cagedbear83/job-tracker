# PRD — Illinois UI Job Search Tracker

## Original Problem Statement
Build a job search tracker app aligned with Illinois Unemployment Insurance laws.
Needs: Claimant Profile, Benefit Week, Work Search Contact (all editable/deletable),
audit log of user interactions, CSV + screenshot import (Indeed etc.), and a
Benefit-Week PDF report mirroring the IDES Work Search form (ADJ034F).

## User Choices
- Auth: JWT custom auth (bcrypt)
- Screenshot import: Gemini 2.5 Pro via Emergent LLM Key
- Report: PDF download (ADJ034F-style)
- IL rules: ≥3 contacts/week, Sun–Sat
- Email reminders: Mailgun (Sun/Wed/Fri/Sat 9 AM CT) on verified domain
- SMS reminders: Twilio (opt-in per claimant)
- Public landing + invite-code signup (case-worker driven growth)

## Architecture
- **Backend**: FastAPI single-file `/app/backend/server.py`, MongoDB via motor.
  All routes under `/api`. JWT Bearer auth. APScheduler runs cron jobs in
  America/Chicago. Mailgun + Twilio integrations with graceful fallback.
- **Frontend**: React + react-router + Tailwind + shadcn/ui + Phosphor icons + Recharts.
  Auth context tracks claimants + activeClaimantId. Header claimant switcher.
  Mobile drawer via Sheet.
- **PDF**: reportlab platypus, mirrors IDES ADJ034F columns.
- **AI Vision**: emergentintegrations LlmChat (gemini-2.5-pro).
- **Email**: Mailgun HTTP API. Verified domain `kmg123enterprises.com` + sandbox fallback.
- **SMS**: Twilio REST client, E.164 format, send-on-success audit logging.

## Personas
- **Claimant** — manages one or many claimant profiles, weeks, contacts.
- **Admin / Case-Worker** — read-only across users, sends invites, monitors integrations.

## Implemented Rounds

### Round 1 — Core MVP
- JWT auth, single Claimant Profile upsert, Benefit Weeks CRUD (Sun–Sat),
  Work Search Contacts CRUD, audit log, CSV import, screenshot OCR (Gemini),
  PDF report (ADJ034F), dashboard, demo seed.

### Round 2 — Reminders + P1/P2
- Multi-claimant per user + active-claimant scoping everywhere
- Admin / case-worker role with `/admin` UI
- CSV export of contacts (per week or all)
- Password reset flow (Mailgun token email)
- Audit edit-diff: `field: old → new` on UPDATEs
- Calendar month-grid view with compliance chips
- Email reminders (4 cron jobs) + per-claimant opt-in + 4 test buttons

### Round 3 — Domain + SMS + Invites + Charts + Polish
- Verified Mailgun domain `kmg123enterprises.com` as active sender with sandbox fallback
- Twilio SMS reminders (opt-in per claimant, E.164 phone)
- Invite-code flow: admin creates → email link → claimant signs up with pre-attached claimant
- Public landing page at `/` with hero, feature grid, case-worker workflow
- Mobile drawer nav via Sheet
- Audit log search + action + entity filters
- Dashboard compliance-trend BarChart (Recharts)
- BSON datetime + TTL indexes on password_resets and invites
- Admin Console split into 3 tabs (Users, Invites, Integrations) with DNS instructions

## Testing
- Round 1: 16/16 backend pytest
- Round 2: 17/17 backend pytest
- Round 3: 16/16 backend pytest
- **Total: 49/49 backend tests passing** + full frontend e2e verified

## Backlog
- P1: Split `server.py` into routers (currently ~1370 lines)
- P1: Escape regex special chars in audit `?q=` parameter (low priority — auth-scoped)
- P1: SMS rate limiting / abuse protection
- P2: Twilio phone-number verification UX (OTP confirm before enabling SMS)
- P2: Search by Twilio phone in claimant table
- P2: Webhooks for Mailgun bounces (auto-disable invalid emails)
- P2: Bulk invite (CSV upload of emails)
- P2: Dashboard timeline filter (last 4/12/52 weeks)
- P3: Native mobile app

## Next Steps
1. Wait for kmg123enterprises.com DNS to fully propagate; verify Mailgun domain status.
2. In Twilio console, verify recipient phone numbers (trial limitation).
3. Split `server.py` into router modules for maintainability.
