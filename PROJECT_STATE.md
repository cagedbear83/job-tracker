# Illinois UI Job Search Tracker — Project State
**Owner:** Kyle Gagen — KMG123 Enterprises LLC  
**Last Updated:** August 14, 2026  
**Version:** 1.3

---

## Quick Reference

| Item | Value |
|---|---|
| Main App URL | https://illinoisjobtracker.app |
| Marketing Site URL | https://www.illinoisjobtracker.com |
| Main App Repo | github.com/cagedbear83/job-tracker |
| Marketing Repo | github.com/cagedbear83/ijt-marketing |
| Backend Host | DigitalOcean App Platform |
| Backend URL | https://illinois-ui-tracker-8wiwq.ondigitalocean.app |
| Database | MongoDB Atlas — cluster: illinois-tracker, db: ides_tracker_db |
| Frontend Host (app) | Vercel — cagedbear83/job-tracker |
| Frontend Host (marketing) | Vercel — cagedbear83/ijt-marketing |
| Domain Registrar | IONOS (illinoisjobtracker.app), name.com (illinoisjobtracker.com) |
| Email | Mailgun — mail.illinoisjobtracker.app |
| SMS | Twilio — +1 (833) 610-0453 (toll-free, verification pending) |
| AI | Google Gemini 2.0 Flash |
| Secrets Manager | Doppler |
| Support Email | support@illinoisjobtracker.app |

---

## 🗓️ Session Update — August 14, 2026

Backend is deploying and running (verified in live DigitalOcean runtime logs). The Aug‑12 deploy blocker is resolved. Major work this session:

### Email verification / CORS / rate limiting
- [x] **Root-caused the verify-email failure:** clicking the link produced a CORS error that was actually a bare `429` from an edge/retry storm plus an app 500. The 401 on `/billing/status` proved app-level CORS was already correct.
- [x] Reworked the flow: verification emails now link to the **backend** (`PUBLIC_BACKEND_URL` + `/api/auth/verify-email`), which verifies and **303-redirects** to `/login?verified=1` (or `?verify_error=...`). No cross-origin XHR → no CORS surface.
- [x] `VerifyEmail.jsx` converted to a redirect shim so already-sent (old-format) links still funnel through the CORS-free flow.
- [x] Login page shows success/error banners on `?verified=1` / `?verify_error=`.
- [x] **Rate-limit key fix:** SlowAPI keyed off the proxy IP, bucketing all users together. Now keys off the left-most `X-Forwarded-For` hop, gated by `TRUST_PROXY` (default on).
- [x] **verify_email 500 fixed:** Motor returns tz-naive datetimes; comparing `verification_token_expires` to an aware `now` threw. Normalized (matches the pattern used elsewhere).

### Registration → profile data
- [x] **Fixed registration data not appearing on the profile.** `register` wrote a profile with ad-hoc keys (`full_name`, `zip`, `is_primary`) that nothing else reads; the app uses the canonical `ProfileIn` schema (`first_name`, `last_name`, `zip_code`, …). Now writes the canonical shape and sets `active_claimant_id`.
- [x] Idempotent **startup migration** upgrades legacy profiles (splits `full_name`, maps `zip`→`zip_code`, drops stale keys).
- [x] Verified the IDES ADJ034F PDF path reads canonical fields — now populates correctly.

### Multi-claimant removal (regular users)
- [x] Removed the entire multi-claimant feature: deleted backend `GET/POST /claimants`, `PUT/DELETE /claimants/{id}`, `POST /claimants/{id}/set-active`.
- [x] Frontend: removed the `/claimants` route, the "Claimants" nav item, the header claimant switcher, and the claimant state from `AuthContext`. Each user has one profile (managed via `/profile`).
- [x] Existing extra profiles are left in place; the app only reads the active one. `pages/Claimants.jsx` is now orphaned — **still needs `git rm`**.

### Subscription tier enforcement (now actually wired)
- [x] Imported `subscription` gate helpers into `server.py` and added gates to every protected route:
  - `gate_metered` → `POST /import/screenshot` (ai_screenshot_import), `GET /reports/benefit-week/{id}` (pdf_exports_per_month)
  - `gate_feature` → calendar create/update (calendar_events), `GET /dashboard/trend` (advanced_analytics), full-history CSV export (csv_export_full_history), `POST /sms/send-otp` (sms_reminders)
  - Document upload: free tier blocked (0 MB), paid tiers get a real total-storage cap
- [x] Metered gates now increment usage counters (fixes the always-empty usage bars).
- [x] Applied `FeatureGate` to the matching UI buttons (Calendar, Import, Documents, WeekDetail PDF) and gated the Dashboard analytics section with a locked upsell card.

### Stripe webhook / tier resolution
- [x] **Critical fix:** `get_user_tier` compared a tz-naive stored `current_period_end` to an aware `now`, throwing for every paid user (500 on billing/status + every gate). Normalized.
- [x] Hardened webhook `current_period_end` extraction to work across Stripe API versions (top-level vs. subscription-items "basil"); never KeyErrors.
- [x] Added a short **grace window** (`SUBSCRIPTION_GRACE_DAYS`, default 3) when `current_period_end` can't be resolved — fails closed to Free instead of granting access indefinitely.

### Dark mode / design tokens
- [x] Properly implemented light/dark. `ThemeProvider` default set to **light** (per design guidelines); toggle + system still work.
- [x] Migrated ~570 hardcoded `bg-white`/`text-zinc`/`#0033A0`/status colors across 22 files to the semantic tokens defined in `index.css` (which already encode the guideline palette). Focus ring + scrollbar made theme-aware.

### Notifications moved to Profile page
- [x] Email reminders toggle + custom reminder email, SMS toggle + phone verification (OTP), and weekly test-send buttons now live on the **Profile** page (ported from the removed Claimants page), wired to the single active profile.

### Account deletion (soft delete)
- [x] **Delete Profile** danger zone on the Profile page: warning dialog requires typing the login email + profile name and checking a confirmation box before a final Delete.
- [x] Backend `POST /account/delete`: verifies email + profile name, **soft-deletes** (access revoked immediately via `deleted` flag in `get_current_user` and `login`), schedules purge after `ACCOUNT_PURGE_GRACE_DAYS` (default 30).
- [x] Daily APScheduler **purge job** hard-deletes all user data across every collection (profiles, benefit_weeks, contacts, calendar_events, document_files, audit_log, password_resets, subscriptions, usage_counters, otp_codes, sms_log, login_attempts, email_events, invites, users). Scheduler now always starts (previously only when Mailgun was set).

### New environment variables (set these in DigitalOcean)
| Variable | Purpose |
|---|---|
| PUBLIC_BACKEND_URL | Backend's own public URL for verification links (e.g. https://illinois-ui-tracker-8wiwq.ondigitalocean.app) |
| TRUST_PROXY | `true` behind DO's proxy so rate limits key off the real client IP |
| SUBSCRIPTION_GRACE_DAYS | Grace days when Stripe period end is unknown (default 3) |
| ACCOUNT_PURGE_GRACE_DAYS | Soft-delete retention before hard purge (default 30) |

---

## Stack

### Backend
| Technology | Detail |
|---|---|
| Language | Python 3.11 |
| Framework | FastAPI |
| Database driver | Motor (async MongoDB) |
| Auth | JWT + bcrypt |
| Email | Mailgun REST API |
| SMS | Twilio |
| AI | Google Gemini 2.0 Flash |
| PDF | pypdf — fills real ADJ034F form |
| Scheduler | APScheduler (AsyncIO) — reminders + account purge |
| Payments | Stripe |
| Deployment | DigitalOcean App Platform via Dockerfile |

### Frontend (Main App)
| Technology | Detail |
|---|---|
| Framework | React 18 (**Vite** — note: earlier docs said CRA; the app uses Vite) |
| Styling | Tailwind CSS v3 + shadcn/ui (semantic CSS-variable tokens, light + dark) |
| Icons | Phosphor Icons |
| Routing | React Router v6 |
| API client | Axios with JWT interceptor + 402 upgrade interceptor |
| Notifications | Sonner (toasts) |
| Theme | next-themes (default light, toggle + system) |
| Deployment | Vercel |

### Marketing Site
| Technology | Detail |
|---|---|
| Framework | Next.js 14 App Router |
| Styling | Tailwind CSS v3 |
| Fonts | Chivo (headings), IBM Plex Sans (body) |
| Theme | next-themes (system dark/light) |
| Deployment | Vercel |

---

## ✅ Completed (carried forward)

### Infrastructure
- [x] React/Vite frontend deployed to Vercel (illinoisjobtracker.app)
- [x] FastAPI backend deployed to DigitalOcean via Dockerfile — **deploy now healthy**
- [x] MongoDB Atlas M0 free tier — cluster illinois-tracker
- [x] Mailgun email — domain mail.illinoisjobtracker.app, SPF/DKIM/DMARC configured
- [x] Doppler secrets management integrated with DigitalOcean, Vercel, GitHub Actions
- [x] Sentry error tracking wired (no-op without DSN)
- [x] CORS configured for app domains (CORSMiddleware wraps outermost — error responses keep headers)
- [x] Security headers middleware
- [x] Rate limiting via SlowAPI — now keyed by real client IP behind proxy
- [x] `.gitignore` — excludes .env, node_modules, .DS_Store

### Authentication & Security
- [x] NIST SP 800-63B-aligned password policy (12-char min, max 64, common password blocklist)
- [x] Account lockout — 5 failed attempts → 15-minute lockout
- [x] Email verification on registration (now via backend redirect flow)
- [x] Password reset flow with token expiry
- [x] bcrypt password hashing
- [x] JWT auth with configurable secret
- [x] Soft-deleted accounts blocked at login and in `get_current_user`

### Main App — Core Features
- [x] Single claimant profile per user (multi-claimant removed)
- [x] Benefit week tracking (Sunday–Saturday periods)
- [x] Work-search contact logging
- [x] Type of Work / Result dropdowns
- [x] ADJ034F PDF generation (pypdf fills real state form — ephemeral)
- [x] CSV export (ephemeral)
- [x] Email reminders via Mailgun (Sun/Wed/Fri/Sat)
- [x] SMS reminders via Twilio (toll-free pending verification)
- [x] AI screenshot import — Google Gemini 2.0 Flash
- [x] Admin panel with RBAC, audit log, impersonation
- [x] Invite-only signup with 14-day single-use codes
- [x] Audit log (append-only)
- [x] APScheduler cron jobs (reminders + account purge)
- [x] **Notifications (email + SMS + phone verification + test sends) on the Profile page**
- [x] **Account deletion (soft delete, 30-day purge, full cascade)**

### Subscription System (now WIRED)
- [x] Tier definitions — Free / Pro / Case Worker
- [x] TIER_LIMITS dict + gating helpers (gate_feature, gate_metered, gate_claimant_limit)
- [x] billing.py — Stripe checkout, portal, webhook (cross-version period-end), billing status
- [x] useSubscription.jsx / UpgradeModal.jsx / FeatureGate.jsx
- [x] **Gate calls wired into all relevant routes; FeatureGate applied to UI**
- [x] **get_user_tier tz + grace-window fixes**
- [x] Stripe test-mode products (3 products, 6 price IDs)

### Pricing (Locked)
| Plan | Monthly | Annual |
|---|---|---|
| Free | $0 | $0 |
| Pro | $9.99/mo | $95.99/yr |
| Case Worker — 1st seat | $19.99/mo | $199.99/yr |
| Case Worker — additional seats | $12.99/mo | $129.99/yr |

### Marketing Site
- [x] (unchanged this session — see prior versions for the full list: Next.js site, all pages, contact proxy, unsubscribe, Mailgun config)

---

## 🔄 In Progress

### Stripe Integration
- [x] Secret key + webhook secret + price IDs in DigitalOcean
- [x] 4 billing routes wired; Mongo indexes for subscriptions + usage_counters
- [x] SubscriptionProvider + UpgradeModalProvider wired into App.jsx
- [x] 402 interceptor in api.js
- [x] **Subscription gate calls added to routes (DONE this session)**
- [ ] Set new env vars in DigitalOcean: `PUBLIC_BACKEND_URL`, `TRUST_PROXY`, `SUBSCRIPTION_GRACE_DAYS`, `ACCOUNT_PURGE_GRACE_DAYS`
- [ ] Test full flow in Stripe test mode with card 4242 4242 4242 4242 (webhook → subscriptions collection → tier resolves)

### Infrastructure
- [ ] Doppler — MongoDB re-setup
- [ ] Doppler — Twilio re-setup
- [ ] Twilio toll-free verification — follow up if not approved within 7 business days
- [ ] `git rm APP/frontend/src/pages/Claimants.jsx` (orphaned after multi-claimant removal)

---

## ⏳ Pending / Not Yet Started

### Admin Panel (Intentionally Held)
- [ ] Seat management UI, reassignment flow, comping (design conversation first)
- [ ] "Claim your account" deep link flow

### Account Lifecycle (partially done)
- [x] Self-serve soft delete + scheduled purge (this session)
- [ ] GDPR 72-hour erasure path (separate from the 30-day self-serve delete)
- [ ] pending_claims + trial_ledger collections/indexes
- [ ] Case-worker org structure (profiles.managed_by, users.org_id + role)
- [ ] 53-week retention warning emails

### Features Not Yet Built
- [ ] AI Resume Review — gating hook exists (ai_resume_review), endpoint not built
- [ ] Calendar events feature — gated + backend routes exist; broader feature TBD
- [ ] Document storage — gated + upload works; S3/offload backend not built
- [ ] Advanced analytics dashboard — gated; trend chart exists, deeper analytics TBD
- [ ] Stripe Elements (inline card form) — replace Checkout redirect
- [ ] SAML SSO — enterprise add-on, build on demand

### Legal & Compliance
- [ ] Attorney review of Claimant_Liability_Release_DRAFT.docx
- [ ] Signature-capture flow for liability release

### Infrastructure / Ops
- [ ] ADJ034F.pdf — place real state form at APP/backend/assets/ADJ034F.pdf
- [ ] Google Cloud billing — attach to unblock Gemini quota
- [ ] Rate limiting on SMS sends to prevent abuse
- [ ] Split server.py into FastAPI routers (P1 — file is large)

---

## Environment Variables Checklist

### Backend (.env + DigitalOcean) — new/changed this session
| Variable | Status |
|---|---|
| PUBLIC_BACKEND_URL | ⚠ **Set in DO** — backend public URL for verification links |
| TRUST_PROXY | ⚠ **Set in DO** — `true` behind DO proxy |
| SUBSCRIPTION_GRACE_DAYS | Optional (default 3) |
| ACCOUNT_PURGE_GRACE_DAYS | Optional (default 30) |
| (all prior vars) | ✅ unchanged — see prior versions |

---

## Known Bugs

| Bug | Severity | Status |
|---|---|---|
| Backend deploy failing / auto-rollback | P0 | **Resolved** — backend running in DO logs |
| CORS blocking error responses | — | **Resolved** — verification reworked to backend-redirect (no CORS surface); rate-limit + tz fixes shipped |
| Registration data not saved to profile | P1 | **Resolved** — canonical schema + migration |
| Paid tiers never resolving (naive/aware datetime in get_user_tier) | P0 | **Resolved** |
| db.claimants → db.profiles at server.py line 431 | P1 | **Resolved / not present** — code uses db.profiles throughout |
| ADJ034F.pdf missing from assets/ | P0 | Open — place manually (download from ides.illinois.gov) |
| Gemini AI hitting quota immediately | P1 | Blocked on Google Cloud billing |
| Twilio toll-free not verified | P2 | Submitted — follow up if >7 days |

---

## How To Update This File

After completing any item:
1. Move it from **Pending** / **In Progress** to **Completed** with `[x]`
2. Update **Last Updated** date + **Version** at the top
3. Add any new open items or bugs discovered
4. Commit: `git commit -m "Update PROJECT_STATE.md"`

This file lives at the root of the `job-tracker` repo. Push it after every session.
