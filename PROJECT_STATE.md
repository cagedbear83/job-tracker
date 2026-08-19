# Illinois UI Job Search Tracker — Project State
**Owner:** Kyle Gagen — KMG123 Enterprises LLC
**Last Updated:** August 19, 2026
**Version:** 1.8

---

## Quick Reference

| Item | Value |
|---|---|
| Main App URL | https://illinoisjobtracker.app |
| Marketing Site URL | https://www.illinoisjobtracker.com |
| Main App Repo | github.com/cagedbear83/job-tracker |
| Marketing Repo | github.com/cagedbear83/ijt-marketing |
| Backend Host | DigitalOcean App Platform. (The unused `APP/render.yaml` Blueprint, plus `docs/DEPLOYMENT.md`/`docs/DEPLOYMENT.html` — a full deployment guide written around it — were deleted Aug 19 after confirming Render was never actually live. `README.md`'s "Backend → Render" line was updated to describe the real DigitalOcean/Dockerfile deploy.) |
| Backend URL | https://illinois-ui-tracker-8wiwq.ondigitalocean.app |
| Database | MongoDB Atlas — cluster: illinois-tracker, db: ides_tracker_db |
| Frontend Host (app) | Vercel — cagedbear83/job-tracker. Build tool is Vite (`vite.config.js`, `vercel.json`'s `"framework": "vite"`) — `craco.config.js` (CRA) is present but stale/superseded, not the active build path |
| Frontend Host (marketing) | Vercel — cagedbear83/ijt-marketing |
| Domain Registrar | IONOS (illinoisjobtracker.app), name.com (illinoisjobtracker.com) |
| Email | Mailgun — mail.illinoisjobtracker.app |
| SMS | ClickSend — migrated from Twilio Aug 19-20 (see Completed section below). Toll-free number registration submitted to ClickSend; number pending carrier approval |
| AI | Google Gemini 2.0 Flash |
| Secrets Manager | Doppler |
| Support Email | support@illinoisjobtracker.app |


---

## Stack

### Backend
| Technology | Detail |
|---|---|
| Language | Python 3.11 |
| Framework | FastAPI |
| Database driver | Motor (async MongoDB) |
| Auth | JWT + bcrypt, single-active-session enforcement |
| Email | Mailgun REST API |
| SMS | ClickSend REST API (migrated from Twilio Aug 19-20) |
| AI | Google Gemini 2.0 Flash |
| PDF | pypdf — fills real ADJ034F form |
| Scheduler | APScheduler (AsyncIO) |
| Payments | Stripe |
| Deployment | DigitalOcean App Platform via Dockerfile |

### Frontend (Main App)
| Technology | Detail |
|---|---|
| Framework | React 18, built with Vite (migrated off Create React App — `craco.config.js` is a stale leftover, not in use) |
| Styling | Tailwind CSS v3 + shadcn/ui |
| Icons | Phosphor Icons |
| Routing | React Router v6 |
| API client | Axios with JWT interceptor |
| Notifications | Sonner (toasts) |
| Error tracking | Sentry (no-op unless REACT_APP_SENTRY_DSN set) |
| Deployment | Vercel |

### Marketing Site
| Technology | Detail |
|---|---|
| Framework | Next.js 14 App Router |
| Styling | Tailwind CSS v3 |
| Fonts | Chivo (headings), IBM Plex Sans (body) |
| Theme | next-themes (system dark/light) |
| Design tokens | Illinois Blue #0033A0, Sharp corners |
| Deployment | Vercel |

---

## ✅ Completed

### Design/Quality Pass, Dark-Mode Fix & Repo Hygiene (Aug 20 — latest session)
- [x] **Marketing Tailwind config fixed (real rendering bugs).** `ijt-marketing/tailwind.config.js` only mapped `background/foreground/muted/border/primary/card`, but `globals.css` also declared `--surface`, `--success`, `--warning`, `--danger`, `--primary-hover`, and pages used utilities built on them. Added those color tokens **and** the missing `fontFamily` (`heading` → Chivo var, `body` → IBM Plex var). Before this: contact-form validation errors didn't render red (`text-danger`), `bg-surface` panels had no background, and `font-heading` on any non-`<h1..h6>` element silently fell back to the body font (Chivo only reached real headings via a CSS element selector). ⚠ Separate repo — needs its own `git commit` + `push` (Vercel redeploys marketing on push)
- [x] **Dark-mode toggle inversion fixed.** `APP/frontend/src/components/Layout.jsx` now drives the sidebar toggle off `resolvedTheme` (what's actually rendered) instead of `theme`, with a `mounted` guard. With `enableSystem` on, `theme` can be the literal `"system"`, so the button's label/icon disagreed with the page — dark/light appeared **inverted** whenever the OS setting drove the color. Now the toggle always matches what's on screen
- [x] **Dashboard chart made theme-aware.** `pages/Dashboard.jsx` Recharts axes/tooltip/cursor/reference-line switched from hardcoded hex (`#52525B`, `#D4D4D8`, `#F4F4F5`, `#0033A0`) to `hsl(var(--...))` tokens, so the compliance-trend chart reads correctly in dark mode (was light-styled only)
- [x] **UI polish + a11y in `index.css`.** Instant button press feedback (tight `scale(0.98)`, no bounce — matches the Swiss/flat system) plus `prefers-reduced-motion` and `prefers-reduced-transparency` media-query support
- [x] **Root `.gitignore` consolidated.** The repo-root `.gitignore` previously covered almost nothing (`.tmp.driveupload/`, `.claude/`, `*.wbk`, `*.bak`, `job-tracker/`); the comprehensive rules lived only in `APP/.gitignore` (which governs just its own subtree). Replaced the root file with full coverage: env/secrets (`.env*`, `*.pem`, `*token.json*`), OS files, node, python (`__pycache__`, `.venv`, `.ruff_cache`, `.pytest_cache`), builds, logs, backups (`*.bak`), archives
- [x] **Backend scratch files removed.** Deleted the committed `server_monolith*.bak` backup, `files.zip`, and ~10 ad-hoc debug scripts (`call_login_direct.py`, `check_login_verify.py`, `check_users.py`, `inspect_jwt.py`, `login_test.py`, `simulate_login.py`, `test_jwt_encode.py`, `test_jwt_encode2.py`, `Test Email.py`, `verify_routes.py`) via a cleanup script; the real tests stay in `tests/`
- [x] **Router split independently re-verified.** Confirmed the `core.py` + `routers/*.py` split imports cleanly and registers the **exact same 61 routes** as the pre-split monolith (route-parity diff + `pyflakes` + `py_compile`), with both middleware, the startup/shutdown handlers, and the SlowAPI limiter all intact. Verified the whole thing boots to the first DB call locally (only stopped by Atlas IP allowlist — a network thing, not code)
- [x] **Incident caught & reverted (no impact):** a Sentry **React onboarding wizard's JavaScript snippet** (`import * as Sentry from "@sentry/react"`, `Sentry.init({...})`, `root.render(<App/>)`) was accidentally pasted into the **Python** `core.py`, and the same wizard created a junk root `package.json`. Caught in `git diff` before commit and discarded with `git restore` — **never committed, never deployed**. The backend already has Python Sentry (`sentry_sdk`) and the frontend already has its own Sentry init, so the paste was redundant anyway

**Git/deploy state (this session):** the app-repo changes above (Layout.jsx, Dashboard.jsx, index.css, root `.gitignore`, backend cleanup) ride on branch **`refactor/split-server`**, which also carries the router split and is **not yet merged to `main`** — merging that one PR ships the split + all these fixes together, and DigitalOcean/Vercel auto-deploy from `main`. The marketing Tailwind fix is in the **separate `ijt-marketing` repo** and needs its own commit/push.

### Admin Platform / RBAC Integration (Aug 17-19)
- [x] Compared standalone `admin_portal` module against `APP/backend`, adapted it (not a drop-in — auth model and route namespace both had to change), and integrated it
- [x] `rbac.py` — new `PlatformRole` enum (`user` / `support_staff` / `platform_admin`), `require_staff`/`require_admin` FastAPI dependencies, `verify_step_up()` re-auth for sensitive actions. Backward-compatible: legacy `role == "admin"` users are treated as `platform_admin` automatically, no forced migration
- [x] `admin_audit.py` — `log_admin_action()` / `query_audit()`, writes to new `db.admin_audit_log` collection (separate from the existing per-user `audit_log`)
- [x] New routers under `/api/admin/platform/*` (namespaced to avoid colliding with the existing `/api/admin/*` routes): `admin_platform_users.py`, `admin_platform_subscriptions.py`, `admin_platform_comps.py`, `admin_platform_refunds.py`, `admin_platform_system.py`, `admin_platform_compliance.py`
- [x] Fixed a real tier-name bug during port: source used `"case_worker"`, this backend's `subscription.Tier.CASEWORKER` is `"caseworker"` (no underscore) — fixed in both the comps router and the frontend
- [x] `admin_disputes.py` — built from scratch (was referenced by `admin_router.py` but never shipped). Required first fixing `Disputes.py`, which had real syntax errors (`tags+[...]` instead of `=`, a `duct` typo for `dict`, dangling `from server import db`) — rewritten as a pure engine module (`record_charge`, `upsert_dispute`, `compute_metrics`, `gather_evidence`, `submit_evidence`)
- [x] Wired `billing.py`'s Stripe webhook handler to actually populate dispute data — added `charge.succeeded` and `charge.dispute.created/updated/closed` handling
- [x] `admin_rbac_migration.py` (backfills `platform_role`, creates indexes) and `bootstrap_admin.py` (promotes one user to `platform_admin` via `BOOTSTRAP_ADMIN_EMAIL` env var) — written, idempotent, **not yet run against production**
- [x] Frontend: `AdminPlatform.jsx` (renamed from `AdminApp.jsx`), `RequireRole.jsx`, `adminApi.js` — rewritten from raw `fetch(credentials:"include")` to the app's actual Bearer-JWT axios client (`src/lib/api.js`); it would have silently 401'd on every request otherwise
- [x] Removed the "view as this user" impersonation feature from the ported admin UI — its module (`./impersonation`) was never included in the source, so it was dead code
- [x] `App.jsx` — new `/admin/platform` route, gated by `RequireRole atLeast="support_staff"`, separate from the existing `/admin` route
- [x] `Layout.jsx` — added "Admin Platform" sidebar/mobile-drawer link (gear icon), shown for `support_staff`/`platform_admin` (via the same legacy-role fallback as `rbac.py`), pushed to the device
- [x] Full backend test suite run before/after integration — zero regressions
- [x] End-to-end smoke test: booted the integrated backend locally (mocked Mongo), simulated a signed Stripe webhook, confirmed a dispute record was created and retrievable through the new router

### SMS Provider Migration: Twilio → ClickSend + Toll-Free Compliance (Aug 19-20)
- [x] Replaced Twilio with ClickSend across the backend. `core.py`'s `send_sms()` now calls ClickSend's REST API (`POST https://rest.clicksend.com/v3/sms/send`, HTTP Basic auth) directly via the `requests` library already used for Mailgun — no new SDK dependency added. Removed `twilio` from `requirements.txt`
- [x] Env vars renamed everywhere they appeared: `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` → `CLICKSEND_USERNAME` / `CLICKSEND_API_KEY` / `CLICKSEND_FROM_NUMBER` (`.env.example`, `docker-compose.yml`; the since-deleted `render.yaml` was also updated before its removal)
- [x] Admin surfaces updated: `admin_platform_system.py`'s `/admin/platform/system/health` check and `admin.py`'s `/admin/integrations/status` endpoint both renamed their `twilio` key to `clicksend`; `AdminPlatform.jsx` needed no change (renders check keys generically), but `Admin.jsx`'s Integrations tab card was hardcoded to "Twilio" and was updated to "ClickSend"
- [x] `routers/sms.py`'s Twilio-trial-account OTP failure message rewritten for ClickSend; `Landing.jsx`'s feature-grid copy ("via Mailgun + Twilio") updated to ClickSend
- [x] Backend tests (`test_round3.py`, `test_round4.py`) updated — assertions against the integrations-status response and code comments referencing Twilio trial numbers
- [x] **Toll-free registration compliance** (new US carrier rules effective Sept 1, 2026, per ClickSend's US/Canada T&C + Privacy Policy guidance):
  - `Register.jsx` — added an unchecked-by-default SMS opt-in checkbox directly below the phone field: business name, "message frequency varies," "message and data rates may apply," STOP/HELP instructions, links to Terms & Privacy. Optional — not required to submit the form
  - `Profile.jsx` SMS card — full opt-in disclosure added around the existing SMS toggle (brand name, frequency, rates, HELP/STOP, clickable Terms/Privacy links opening in a new tab), matching ClickSend's required-elements checklist
  - `PrivacyPolicy.jsx` / `Terms.jsx` (app) — SMS sections rewritten with explicit Data Collection / Usage / Sharing / Opt-Out / Rates subsections (including the required "we do not sell or share your number for third-party marketing" line); Twilio references swapped to ClickSend; the "⚠ ATTORNEY REVIEW REQUIRED" header comment removed from both files per Kyle's request
  - `ijt-marketing/app/terms/page.tsx` + `app/privacy/page.tsx` — previously had **no** SMS-specific language at all; added matching "SMS text messaging terms" / "SMS communications" sections, reusing the pages' existing `{site.company}`/`{site.name}` tokens
  - Backend consent wiring: `RegisterIn.sms_opt_in` (core.py) flows through `auth.py`'s `/auth/register` handler into `profile_doc.sms_enabled`, plus a `sms_opt_in_at` timestamp and an `SMS_OPT_IN` audit-log entry when checked — consent evidence for carrier/TCPA purposes. No SMS is ever sent from an opted-in-but-unverified profile — the reminder-send path still gates on `sms_verified` (OTP), so this only records consent, it doesn't bypass verification
  - Provided Kyle with the "describe who you message and why" carrier-application text and 3 representative sample messages (1 OTP + 2 reminder) for the ClickSend toll-free application form
- [x] `render.yaml` deleted by Kyle (Aug 19) — see Quick Reference and Known Bugs

### Infrastructure
- [x] React/Vite frontend deployed to Vercel (illinoisjobtracker.app)
- [x] FastAPI backend deployed to DigitalOcean via Dockerfile
- [x] MongoDB Atlas M0 free tier — cluster illinois-tracker
- [x] Mailgun email — domain mail.illinoisjobtracker.app, SPF/DKIM/DMARC configured
- [x] Doppler secrets management integrated with DigitalOcean, Vercel, GitHub Actions
- [x] Sentry error tracking wired (no-op without DSN)
- [x] CORS configured for app domains
- [x] Security headers middleware (X-Content-Type-Options, X-Frame-Options, etc.)
- [x] Rate limiting via SlowAPI (login, register, forgot password, reminder test)
- [x] `.gitignore` — root file consolidated Aug 20 to full coverage (env/secrets, OS, node, python caches, builds, logs, `*.bak`, archives); previously the real rules lived only in `APP/.gitignore`

### Authentication & Security
- [x] NIST SP 800-63B-aligned password policy (12-char min, max 64, common password blocklist)
- [x] Account lockout — 5 failed attempts → 15-minute lockout
- [x] Single-active-session enforcement via session_id/sid JWT claim
- [x] Email verification on registration
- [x] Password reset flow with token expiry
- [x] bcrypt password hashing
- [x] JWT auth with configurable secret

### Main App — Core Features
- [x] Multi-claimant profile management (scoped per user)
- [x] Benefit week tracking (Sunday–Saturday periods)
- [x] Work-search contact logging
- [x] Type of Work dropdown (Full-time, Part-time, Independent Contractor, Temporary/Seasonal, Contract-to-hire)
- [x] Result dropdown (Applied, Awaiting Outcome, Interview Scheduled, Interviewing, Hired, Networking, Not Hired, Not Hiring/Did not Apply)
- [x] ADJ034F PDF generation (pypdf fills real state form — ephemeral, never stored)
- [x] CSV export (ephemeral, never stored)
- [x] Loading/error/empty/success states on WeekDetail page
- [x] Email reminders via Mailgun (Sun/Wed/Fri/Sat schedule)
- [x] SMS reminders via ClickSend (toll-free number registration submitted — pending carrier approval)
- [x] AI screenshot import — Google Gemini 2.0 Flash
- [x] Admin panel with RBAC (PlatformRole), audit log — impersonation feature dropped during the Aug 17-19 integration (dead reference, module never existed)
- [x] Invite-only signup with 14-day single-use codes
- [x] Audit log (append-only, timestamp + user)
- [x] APScheduler cron jobs for reminders
- [x] Emergent branding fully removed
- [x] Demo credentials removed from login page

### Subscription System (Designed & Coded — Not Yet Wired)
- [x] Tier definitions — Free / Pro / Case Worker
- [x] TIER_LIMITS dict — all feature gates in one place
- [x] subscription.py — gating helpers (gate_feature, gate_metered, gate_claimant_limit)
- [x] billing.py — Stripe checkout, customer portal, webhook handler, billing status, now also feeds dispute data to `Disputes.py`
- [x] trial.py — 14-day Pro trial, card-upfront, one-per-person (email + card fingerprint), farmer detection
- [x] account_lifecycle.py — soft delete (30-day), GDPR erasure (72-hour), purge executor
- [x] account_lifecycle_cascade.py — cascade map for all collections
- [x] caseworker_orphan.py — removal/reassignment, orphan migration, claim-account flow
- [x] useSubscription.jsx — React context/hook for tier/usage/feature checks
- [x] UpgradeModal.jsx — pricing modal with monthly/annual toggle, fires on HTTP 402
- [x] FeatureGate.jsx — wraps buttons to lock/disable when feature not on tier
- [x] DeleteAccountSection.jsx — individual-users-only, type-email-to-confirm, GDPR path
- [x] Stripe test-mode products created (3 products, 6 price IDs)
- [x] stripe.env.filled — all 6 price IDs filled, SK and webhook secret still need adding

### Pricing (Locked)
| Plan | Monthly | Annual |
|---|---|---|
| Free | $0 | $0 |
| Pro | $9.99/mo | $95.99/yr (~20% off) |
| Case Worker — 1st seat | $19.99/mo | $199.99/yr (~17% off) |
| Case Worker — additional seats | $12.99/mo | $129.99/yr (~17% off) |

### Marketing Site (illinoisjobtracker.com)
- [x] Next.js App Router project scaffolded and deployed to Vercel
- [x] Domain connected — www.illinoisjobtracker.com (308 redirect from bare domain)
- [x] Chivo + IBM Plex Sans fonts wired via next/font/google
- [x] Illinois Blue (#0033A0), sharp corners, design guidelines applied globally
- [x] Dark/light mode via next-themes (restored after accidental removal)
- [x] SiteNav — IL bordered logo, capitalized nav links, Sign In/Get Started linked to app
- [x] SiteFooter — IL bordered logo, product/company/legal columns, IDES disclaimer banner
- [x] Landing page — three tiers, 14-day trial, benefits section, all paid features shown, CTA button white on blue fixed
- [x] Features page — 10 features in 4 groups, no checkmarks, Illinois blue headings
- [x] Pricing page — three cards, monthly/annual toggle, aligned prices and buttons
- [x] FAQ page — 16 questions, accordion, Refund Policy + Privacy Policy hyperlinked
- [x] How It Works page — 4 steps, Illinois blue heading, correct wording, Start Free linked to app
- [x] About page — Illinois blue heading, Try It Free links to landing
- [x] Contact page — full form (First/Last Name, email validation, 10-digit phone, reason dropdown, message), Next.js server-side proxy to backend, two confirmation emails, reference numbers (IJT-XXX-000000)
- [x] Privacy Policy — updated for three tiers, AI ephemerality, GDPR/CCPA, Case Worker data handling; gained a new SMS communications section Aug 19-20 (see ClickSend migration above)
- [x] Terms of Service — updated for three tiers, trial terms, one-trial-per-person rule; gained a new SMS text-messaging terms section Aug 19-20 (see ClickSend migration above)
- [x] Refund Policy — all sales final, cancel-manually language, seat change proration
- [x] IDES Disclaimer — Not A Government Service in Illinois blue
- [x] Unsubscribe page — branded custom page at /unsubscribe
- [x] Mailgun unsubscribe template — custom branded HTML template set in Mailgun dashboard
- [x] Mailgun unsubscribe footer — turned OFF globally (all emails are transactional, not marketing)
- [x] Mailgun click/open tracking — OFF (prevents SSL error on email links)
- [x] /api/contact route in server.py — sends two emails with reference numbers
- [x] Next.js proxy route (app/api/contact/route.ts) — eliminates CORS issue entirely
- [x] CORS updated for illinoisjobtracker.com and www.illinoisjobtracker.com
- [x] Mailgun transactional emails — unsubscribe link and tracking disabled via h:List-Unsubscribe and o:tracking headers

### Frontend Code Quality (Aug 11-12)
- [x] Fixed all 20 ESLint errors blocking CI across 13 files
- [x] Removed unused vars/imports (Layout, UpgradeModal, useSubscription, Dashboard, InviteSignup, Calendar, Documents, WeekDetail)
- [x] Fixed a11y violations — keyboard accessibility added to Calendar day cells and Documents drop zone (role/tabIndex/onKeyDown)
- [x] Fixed false-positive a11y warnings in shadcn components (alert.jsx, pagination.jsx) with correctly-placed eslint-disable comments
- [x] Fixed react/no-unknown-property for cmdk-input-wrapper in command.jsx
- [x] Removed unused actionTypes constant in use-toast.js
- [x] Fixed empty catch block in AuthContext.jsx
- [x] Documents.jsx line 131 had `setSaving: setUploading(true)` — a stray labeled statement left over from a refactor
- [x] Properly fixed exhaustive-deps warning in AuditLog.jsx using useCallback instead of suppression
- [x] Frontend lint & build CI now passing

### Repository Cleanup (Aug 12)
- [x] Removed nested duplicate repo at job-tracker/job-tracker (full clone of itself with its own .git) — likely cause of recurring git divergence issues
- [x] VS Code Source Control now shows single clean repo

### Documents Produced
- [x] Subscription_Decisions_Summary.docx (v8)
- [x] Claimant_Liability_Release_DRAFT.docx (needs attorney review)
- [x] Illinois_UI_Tracker_Handoff.docx (full project handoff)
- [x] COMPLETE_FILE_HANDOFF.md (all code files bundled)

---

## 🔄 In Progress

### Stripe Integration
- [x] STRIPE_SECRET_KEY added to DigitalOcean (test mode)
- [x] STRIPE_WEBHOOK_SECRET added to DigitalOcean (test mode)
- [x] TRIAL_LEDGER_SALT generated and added to DigitalOcean
- [x] Stripe webhook endpoint created in dashboard
- [x] stripe==11.1.0 added to requirements.txt
- [x] 4 billing routes wired into server.py (/billing/checkout, /billing/portal, /billing/status, /webhooks/stripe)
- [x] MongoDB indexes added for subscriptions + usage_counters
- [x] SubscriptionProvider + UpgradeModalProvider already wired into App.jsx (note: file is App.jsx not App.js)
- [x] 402 interceptor already present in api.js
- [x] Webhook handler extended (Aug 17-19) to also feed `Disputes.py` on `charge.succeeded` / `charge.dispute.*` events — needed for the new admin disputes panel to show real data
- [x] Backend deployment failing — DigitalOcean rolls back on every deploy attempt. Code verified correct locally (billing.py + subscription.py import cleanly, server.py has app object + all routes, 2685 lines). Suspected DigitalOcean build cache serving stale image. Next step: force cache invalidation via requirements.txt change. Confirm still relevant now that the backend has been split into `core.py`/`routers/*.py`
- [x] Add subscription gate calls to existing routes (calendar, screenshot import, PDF export, claimant creation) — NOT STARTED, this is why nothing is gated in the app yet
- [x] Test full flow in Stripe test mode with card 4242 4242 4242 4242
- [x] Add `charge.dispute.created` / `charge.dispute.updated` / `charge.dispute.closed` to the subscribed events list on the Stripe webhook endpoint in the dashboard (code handles them now, but the endpoint needs to actually be subscribed to receive them)

### Admin Platform Go-Live (Aug 17-19)
- [ ] Confirm live frontend domain and log in as an existing admin account, then navigate to `/admin/platform` to verify the new dashboard renders and loads data — not yet confirmed working against a real deployed or local environment
- [ ] Decide whether to run `admin_rbac_migration.py` / `bootstrap_admin.py` — likely unnecessary for a single-admin setup since `rbac.py` already treats legacy `role == "admin"` as `platform_admin`; only needed for a distinct `support_staff` account or a `platform_admin` account without the legacy role
- [ ] Push the integration to `main` and confirm DigitalOcean picks up the deploy
- [ ] Verify env vars: `BOOTSTRAP_ADMIN_EMAIL` (optional, only if running bootstrap_admin.py), `PLATFORM_COMP_CAP`, `SENTRY_DASHBOARD_URL`, `APP_ENV` (all documented in `.env.example`, all optional)

### Infrastructure
- [ ] Doppler — MongoDB re-setup
- [ ] Doppler — set `CLICKSEND_USERNAME` / `CLICKSEND_API_KEY` / `CLICKSEND_FROM_NUMBER`, replacing the old `TWILIO_*` secrets
- [ ] ClickSend toll-free number registration — submitted, awaiting carrier approval; follow up if not approved within the usual review window
- [ ] Once approved, decide whether to update the live SMS message templates in `core.py` (OTP + reminder text) to literally include "Reply STOP to opt out" — the sample messages submitted to ClickSend include it, but the running code currently doesn't (see Open Decisions)

---

## ⏳ Pending / Not Yet Started

### Admin Panel (Intentionally Held)
- [ ] Design conversation with Kyle first (seat management UI, reassignment flow, comping)
- [ ] Seat management UI — add/remove seats, Stripe quantity sync
- [ ] Case worker reassignment interface — auto-distribute or manual per-claimant
- [ ] Platform admin comping — test mode unlimited, production cap (number TBD when beta list exists)
- [ ] "Claim your account" deep link flow (email → auto-login → auto-generate PDF)
- [ ] Role-grant flow in the new admin-platform UI — right now only `bootstrap_admin.py` (CLI) can create a `platform_admin`; promoting additional staff still needs a script, not a UI action

### Account Lifecycle Wiring
- [ ] Wire routes into server.py: /account/delete, /account/gdpr-erasure, /admin/caseworkers/{id}/remove, /claim/{token} (public)
- [ ] Add 4 scheduled jobs to APScheduler (soft-delete purge, GDPR purge, pending-claim purge, 53-week retention deletion)
- [ ] Add pending_claims + trial_ledger collections/indexes
- [ ] Add profiles.managed_by field and users.org_id + role for case-worker org structure
- [ ] Render DeleteAccountSection at bottom of profile page (individual users only)
- [ ] 53-week retention warning emails (14d, 7d, 24h) with deep-link auto-login + auto-generate PDF

### Features Not Yet Built
- [ ] AI Resume Review — gating hook exists (ai_resume_review), endpoint not built. Design: upload flow, Gemini prompt, ephemeral handling, disclaimer shown
- [ ] Calendar events feature — gated, backend not built
- [ ] Document storage — gated, S3/storage backend not built
- [ ] Advanced analytics dashboard — gated, not built
- [ ] Stripe Elements (inline card form) — replace Stripe Checkout redirect with embedded form
- [ ] Annual billing UI toggle in upgrade flow
- [ ] SAML SSO — parked as enterprise add-on, $99/mo flat, build on demand

### Legal & Compliance
- [ ] Attorney review of Claimant_Liability_Release_DRAFT.docx before use with any real claimant
- [ ] Signature-capture flow for liability release (when case worker adds a claimant)
- [ ] Add AI Resume Review section to IJT_Compliance_Requirements.md once feature is designed

### Marketing Site — Remaining
- [ ] Verify all pages live and links working end-to-end
- [ ] Test contact form emails arriving consistently after Mailgun tracking changes
- [ ] Verify the new SMS T&C/Privacy sections render correctly on the live marketing site (added Aug 19-20, not yet deployed/verified in production)

### Infrastructure / Ops
- [ ] ADJ034F.pdf — place real state form at APP/backend/assets/ADJ034F.pdf (download from ides.illinois.gov)
- [ ] Google Cloud billing — attach billing to unblock Gemini free tier quota
- [ ] Inline Stripe Elements card form (replace Checkout redirect)
- [ ] Fix db.claimants → db.profiles at server.py line 431 (orphaned collection bug) — note: current backend is split into routers, confirm this line reference still applies to whichever file now owns that logic
- [x] Rate limiting on SMS sends to prevent abuse — already implemented via `SMS_MIN_INTERVAL_MINUTES` in `send_sms_rate_limited()` (core.py); confirmed while working on the ClickSend migration (Aug 19-20)
- [x] Split server.py into FastAPI routers — done. `APP/backend` is now `core.py` + `server.py` (composition root) + `routers/*.py`; the old monolith is backed up at `APP/server_monolith.py.bak`

---

## Open Decisions

| Item | Status |
|---|---|
| Platform admin comp cap | Left open — revisit when beta-tester list exists |
| AI Resume Review feature build | Placeholder only — resume after Stripe is live |
| Partial seat removal behavior | When a CW is removed and remaining CWs take their claimants — auto-even-split or manual choice confirmed. Edge case: what happens to claimants if org drops from e.g. 5 seats to 3 to cut costs? Blocked — downgrade action. |
| Annual billing UI | Design confirmed, build after first paying customers |
| Layer 2 IP anomaly detection | Deferred — revisit when user base grows |
| SMS message template STOP/HELP language | Open — the 3 sample messages submitted to ClickSend for toll-free approval include "Reply STOP to opt out," but the live OTP/reminder templates in `core.py` don't yet. Decide whether to update the running templates to match what was submitted. |

---

## Environment Variables Checklist

### Backend (.env + DigitalOcean)
| Variable | Status |
|---|---|
| MONGO_URL | ✅ Set |
| DB_NAME | ✅ Set (ides_tracker_db) |
| JWT_SECRET | ✅ Set |
| ADMIN_EMAIL | ✅ Set |
| ADMIN_PASSWORD | ✅ Set |
| MAILGUN_API_KEY | ✅ Set |
| MAILGUN_DOMAIN | ✅ Set (mail.illinoisjobtracker.app) |
| MAILGUN_FROM | ✅ Set |
| CLICKSEND_USERNAME | ⚠ Not yet set — replaces TWILIO_ACCOUNT_SID (Doppler) |
| CLICKSEND_API_KEY | ⚠ Not yet set — replaces TWILIO_AUTH_TOKEN (Doppler) |
| CLICKSEND_FROM_NUMBER | ⚠ Not yet set — pending ClickSend toll-free approval; replaces TWILIO_FROM_NUMBER (Doppler) |
| GEMINI_API_KEY | ⚠ Needs billing attached in Google Cloud |
| FRONTEND_URL | ✅ Set (https://illinoisjobtracker.app) |
| CORS_ORIGINS | ✅ Updated (includes .com and .app domains) |
| STRIPE_SECRET_KEY | ✅ Set (test mode) |
| STRIPE_WEBHOOK_SECRET | ✅ Set (test mode) |
| STRIPE_PRICE_PRO_MONTHLY | ✅ price_1TpYJcB9Z4CA8NX58NcWqfJ4 |
| STRIPE_PRICE_PRO_ANNUAL | ✅ price_1TpYJcB9Z4CA8NX567lyzodK |
| STRIPE_PRICE_CW_FIRST_MONTHLY | ✅ price_1TpYPDB9Z4CA8NX5ZUclGUzl |
| STRIPE_PRICE_CW_FIRST_ANNUAL | ✅ price_1TpYPDB9Z4CA8NX52oyqh9hd |
| STRIPE_PRICE_CW_ADDL_MONTHLY | ✅ price_1TpYTYB9Z4CA8NX5mBgesueK |
| STRIPE_PRICE_CW_ADDL_ANNUAL | ✅ price_1TpYTYB9Z4CA8NX5ij6YSoBS |
| TRIAL_LEDGER_SALT | ✅ Set |
| BOOTSTRAP_ADMIN_EMAIL | New (Aug 17-19), optional — only needed if running bootstrap_admin.py |
| PLATFORM_COMP_CAP | New (Aug 17-19), optional — production comp cap for admin platform, TBD |
| SENTRY_DASHBOARD_URL | New (Aug 17-19), optional |
| APP_ENV | New (Aug 17-19), optional |

### Frontend — Main App (Vercel)
| Variable | Status |
|---|---|
| REACT_APP_BACKEND_URL | ✅ Set |
| REACT_APP_SENTRY_DSN | ⚠ Optional — no-op if not set |

---

## Key Files Reference

### Backend (APP/backend/)
| File | Purpose |
|---|---|
| server.py | Main FastAPI app — routes; ⚠ this doc previously described it as one ~2,500-line file, but the version touched Aug 17-19 wires routers from `core.py`/`routers/*.py` — confirm current structure |
| subscription.py | Tier limits, gating helpers, usage metering |
| billing.py | Stripe checkout, webhook, portal — now also feeds Disputes.py on charge/dispute webhook events |
| trial.py | 14-day Pro trial, farmer detection |
| account_lifecycle.py | Soft delete + GDPR erasure |
| account_lifecycle_cascade.py | Cascade map — what deletes what |
| caseworker_orphan.py | Orphan migration + claim flow |
| rbac.py | New (Aug 17-19) — PlatformRole enum, require_staff/require_admin, step-up re-auth |
| admin_audit.py | New (Aug 17-19) — admin action audit log, separate from per-user audit_log |
| Disputes.py | Rewritten (Aug 17-19) — dispute engine (record_charge, upsert_dispute, compute_metrics, evidence submission), was broken/unshipped before |
| routers/admin_disputes.py | New (Aug 17-19) — /api/admin/platform/disputes endpoints |
| routers/admin_platform_*.py | New (Aug 17-19) — users, subscriptions, comps, refunds, system, compliance |
| admin_rbac_migration.py | New (Aug 17-19) — backfills platform_role, creates indexes. Not yet run against production |
| bootstrap_admin.py | New (Aug 17-19) — promotes one user to platform_admin via BOOTSTRAP_ADMIN_EMAIL. Not yet run against production |
| core.py | Shared app state, models, helpers. `send_sms()` migrated to ClickSend's REST API (Aug 19-20); `RegisterIn`/`Profile` models gained `sms_opt_in` / `sms_opt_in_at` |
| routers/sms.py | OTP send/verify endpoints — Twilio-trial error message rewritten for ClickSend (Aug 19-20) |
| routers/auth.py | Registration handler — now seeds SMS opt-in consent (`sms_enabled`, `sms_opt_in_at`, `SMS_OPT_IN` audit log entry) from the Register-page checkbox (Aug 19-20) |
| assets/ADJ034F.pdf | ⚠ MISSING — must be placed manually |
| requirements.txt | Python dependencies — `twilio` removed Aug 19-20 (ClickSend goes over the existing `requests` dependency) |
| Dockerfile | Container definition |

### Frontend — Main App (APP/frontend/src/)
| File | Purpose |
|---|---|
| pages/WeekDetail.jsx | Benefit week + contacts, loading/error states |
| pages/AdminPlatform.jsx | New (Aug 17-19) — admin-platform dashboard (users, comps, refunds, disputes, system, compliance panels) |
| components/RequireRole.jsx | New (Aug 17-19) — front-end role gate for the admin-platform route |
| lib/adminApi.js | New (Aug 17-19) — admin-platform API client, uses the shared Bearer-JWT axios client |
| components/Layout.jsx | Updated (Aug 19) — added sidebar/mobile-drawer link to /admin/platform for support_staff/platform_admin. Updated (Aug 20) — dark-mode toggle now uses `resolvedTheme` + mount guard (fixes inverted light/dark) |
| pages/Dashboard.jsx | Updated (Aug 20) — Recharts axes/tooltip/reference-line use `hsl(var(--...))` tokens so the compliance chart is correct in dark mode |
| index.css | Updated (Aug 20) — button press feedback + `prefers-reduced-motion`/`prefers-reduced-transparency` support |
| hooks/useSubscription.jsx | Tier/usage/feature checks |
| components/UpgradeModal.jsx | Pricing modal, fires on 402 |
| components/FeatureGate.jsx | Locks gated buttons |
| components/DeleteAccountSection.jsx | Delete account UI |
| context/AuthContext.jsx | Auth state, sessionStorage |
| lib/api.js | Axios client + JWT interceptor |
| pages/Register.jsx | Updated (Aug 19-20) — added unchecked-by-default SMS opt-in checkbox below the phone field, for ClickSend toll-free compliance |
| pages/Profile.jsx | Updated (Aug 19-20) — SMS card now carries full opt-in disclosure (brand name, frequency, rates, STOP/HELP, Terms/Privacy links) around the existing SMS toggle |
| pages/PrivacyPolicy.jsx, pages/Terms.jsx | Updated (Aug 19-20) — SMS sections rewritten for ClickSend (Data Collection/Usage/Sharing/Opt-Out); "⚠ ATTORNEY REVIEW REQUIRED" header comment removed |
| pages/Admin.jsx | Updated (Aug 19-20) — Integrations tab SMS provider card changed from hardcoded "Twilio" to "ClickSend" |
| pages/Landing.jsx | Updated (Aug 19-20) — feature-grid copy "Mailgun + Twilio" → "Mailgun + ClickSend" |

### Marketing Site (ijt-marketing/)
| File | Purpose |
|---|---|
| lib/site.ts | All copy, pricing, nav, FAQs — edit here |
| app/layout.tsx | Root layout — SiteNav + SiteFooter, Chivo + IBM Plex Sans fonts |
| app/globals.css | Design token CSS variables (light + dark mode) |
| tailwind.config.js | Illinois Blue + design color tokens and `font-heading`/`font-body` families. ⚠ Aug 20: these were actually **missing** and pages referenced them anyway — added `surface`/`success`/`warning`/`danger`/`primary-hover` colors and the `heading`/`body` `fontFamily` entries (needs commit/push) |
| components/site-nav.tsx | Top navigation, IL bordered logo, theme toggle |
| components/site-footer.tsx | Footer, IDES disclaimer banner |
| components/ui-bits.tsx | Button (primary/outline/white), Check, Section, PageHeader |
| app/pricing/page.tsx | Three-tier pricing with monthly/annual toggle |
| app/contact/page.tsx | Contact form — posts to Next.js proxy |
| app/api/contact/route.ts | Next.js server-side proxy → FastAPI backend (eliminates CORS) |
| app/unsubscribe/page.tsx | Branded unsubscribe confirmation page |
| app/terms/page.tsx, app/privacy/page.tsx | Updated (Aug 19-20) — gained new SMS text-messaging sections (previously had none), for ClickSend toll-free compliance |

---

## Known Bugs

| Bug | Severity | Status |
|---|---|---|
| db.claimants → db.profiles at server.py line 431 | P1 | Open — fix before production claimants. ⚠ confirm this line reference still applies given the router split |
| ADJ034F.pdf missing from assets/ | P0 | Must be placed manually (download from ides.illinois.gov) |
| Gemini AI hitting quota immediately | P1 | Blocked on Google Cloud billing |
| ClickSend toll-free number not yet approved | P2 | Registration submitted (migrated from Twilio Aug 19-20) — follow up if not approved within the usual review window |
| Git divergence between PC and Mac | Resolved | Root cause was nested duplicate repo, now deleted. Still: always pull before pushing |
| Backend deploy failing / auto-rollback | P0 | Code verified correct locally. Suspected DigitalOcean stale build cache. Try requirements.txt cache-bust. Confirm still relevant now that the backend has been split into `core.py`/`routers/*.py` |
| CORS blocking error responses | Fixed (pending deploy) | CORSMiddleware was registered AFTER security_headers middleware, so error responses lost CORS headers. Reordered so CORS wraps outermost |
| Marketing site → app registration flow | Untested | Pro purchase link goes to /register but email verification was blocked by the CORS bug |
| admin_portal's original adminApi.js used cookie auth (`credentials:"include"`) | Fixed (Aug 17-19) | This app uses Bearer JWT via axios interceptor, not cookies — every admin-platform request would have silently 401'd. Rewritten to use the shared api client before it ever shipped |
| Disputes.py had unshipped syntax errors | Fixed (Aug 17-19) | `tags+[...]` instead of `=`, `duct` typo for `dict`, dangling `from server import db` — rewritten as a pure engine module |
| Stale Render blueprint/docs implied the backend was hosted on Render | Fixed (Aug 19) | `APP/render.yaml` was never an active deploy — Render was never actually live. Deleted it along with `docs/DEPLOYMENT.md`/`docs/DEPLOYMENT.html` (both written entirely around Render); fixed the one line in `README.md` that referenced it. DigitalOcean is the confirmed live backend host |
| Marketing Tailwind utilities resolved to nothing (`text-danger`, `bg-surface`, `font-heading`, `bg-primary-hover`, etc.) | Fixed (Aug 20) | `ijt-marketing/tailwind.config.js` never defined those color tokens or the `heading`/`body` font families, though pages used them everywhere — errors weren't red, surface panels had no bg, display font fell back silently. Config updated; ⚠ needs commit/push to deploy |
| App dark-mode toggle inverted when OS drives the theme | Fixed (Aug 20) | `Layout.jsx` toggle read `theme` (which is `"system"` under `enableSystem`) instead of `resolvedTheme`, so label/icon disagreed with the rendered colors. Now uses `resolvedTheme` + mount guard. On branch `refactor/split-server`, pending merge/deploy |
| Dashboard compliance chart light-styled in dark mode | Fixed (Aug 20) | Recharts axes/tooltip/reference-line used hardcoded hex; migrated to `hsl(var(--...))` tokens |
| Sentry React JS snippet pasted into Python `core.py` | Fixed (Aug 20) | Sentry onboarding wizard's browser-SDK snippet landed in the backend file (would crash on startup) and made a junk root `package.json`. Caught in `git diff`, `git restore`d — never committed or deployed |
| Stale Twilio references throughout backend, admin UI, and legal pages | Fixed (Aug 19-20) | Full sweep after switching SMS providers: `core.py` send_sms, requirements.txt, .env.example, docker-compose.yml, admin_platform_system.py, admin.py, Admin.jsx, Landing.jsx, tests — all migrated to ClickSend. App and marketing-site legal pages gained ClickSend-specific SMS compliance language for the Sept 1, 2026 toll-free carrier rules |

---

## How To Update This File

After completing any item:
1. Move it from **Pending** or **In Progress** to **Completed** with a `[x]`
2. Update **Last Updated** date at the top
3. Add any new open items or bugs discovered
4. Commit: `git commit -m "Update PROJECT_STATE.md"`

This file lives at the root of the `job-tracker` repo. Push it after every session.
