# Illinois UI Job Search Tracker — Project State
**Owner:** Kyle Gagen — KMG123 Enterprises LLC
**Last Updated:** August 20, 2026
**Version:** 1.16

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

## 📋 Site Fixes Punch List (from Site_Fixes_20260819.docx)

Kyle's Aug 19 fixes doc, tracked item-by-item. Working through it together, one item at a time, ASAP items first. Updated as each is completed — see the dated entries under **✅ Completed** below for the actual detail on finished items.

### MAIN SITE
- [x] **Full-Stack — session logout (ASAP)** (Aug 20) — "App doesn't log the user out when they exit the browser or after a certain amount of time" — fixed via a full access/refresh-token rework, see "Session Security / Auth Hardening" under Completed
- [x] **Calendar** (Aug 20) — reminder engine, 5-business-day work-search follow-up, and the bi-weekly certification reminder cutoff all built — see "Calendar Reminder Engine" under Completed
- [ ] **Documents** — confirm IDES-document upload/encrypted-storage is actually wired up; malware-scan uploads + enforce PDF/.doc/.docx/.jpg + size limit; convert uploads to PDF; compress uploads to save space
- [x] **Register page** (Aug 20) — branding/disclaimer added, phone auto-format, required-field marking, and the "next certification date" question with 26-week auto-seed — see "Register Page — Branding, Validation & Certification-Date Seeding" under Completed
- [x] **VerifyEmail page** (Aug 20) — branded header + disclaimer added, both states polished — see "VerifyEmail Page Redesign" under Completed
- [ ] **Dashboard** — analytics/visual breakdowns of job-search trends and success rates
- [x] **Week Detail — ADJ034F report bug (ASAP)** (Aug 20) — generated PDF only populated Last Name and ID/SSN; root cause found and fixed, see "ADJ034F Report Field-Population Fix" under Completed
- [ ] **Week Detail — remaining items** — add a Tags field to the work-search contact popup; build out Filters (Result/Type/Date/Contact Method, saved views, active-filter chips, live counts) and Search (global keyword + faceted); "Generating Report…" loading state on the PDF button

### MARKETING SITE
- [ ] **FAQ page** — styling pass (remove top letter index, color "Questions? Answered." Illinois Blue); add/update the 9 listed Q&As; replace the bottom disclaimer with the new IDES-independence wording

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

### VerifyEmail Page Redesign (Aug 20 — latest session)
Fixes the VerifyEmail punch-list item. This page is a small, mostly-transient shim — for current registrations the verification link goes straight to the backend, which redirects on to `/login`; this page only renders for older pre-change email links, and even then only briefly (it immediately forwards to the backend once it reads the token), so a full Login/Register-style two-column hero layout would be overkill for a screen almost nobody actually looks at for more than a second. Scoped the redesign to matching the same branding quality instead:
- [x] Added the "IL" badge + "Illinois UI Job Search Tracker" header treatment (same visual pattern as the reminder emails' header — see `core.py`'s `_reminder_html`), replacing the old plain color-strip `brand-bar`
- [x] Added the "Unofficial tool — not affiliated with IDES" disclaimer footer, matching `InviteSignup.jsx`'s wording — this page had no IDES disclaimer at all before
- [x] Polished both states it actually renders: the error ("no token") state now uses a proper circled ✕ icon (destructive-token styling, matching the rest of the app) instead of bare text, plus a one-line explanation of what to do next; the verifying/spinner state got a slightly heavier spinner stroke for visibility. (A "success" state was never rendered here — the page redirects via `window.location.replace` before anything past the spinner would show — so nothing was added there)
- [x] JSX syntax verified via an esbuild parse (no dev environment available to run the project's own ESLint here)
- [ ] **Not yet done:** file written directly into the local working tree, not yet committed/pushed

### Calendar Reminder Engine (Aug 20 — latest session)
Fixes the Calendar punch-list item. Was blocked on Register's certification-date capture (built earlier this session — see below), since there was previously no data to build certification reminders on top of. All new code lives in `core.py`'s new "Calendar Event Reminders" section, `server.py`'s scheduler block, and `routers/contacts.py`.
- [x] **Generic reminder engine, not certification-specific.** `_broadcast_event_reminders(kind)` scans `calendar_events` daily at 8AM CT for anything landing 3 days out ("3day") or today ("morning") and emails a reminder — works for certification, IDES interview, appeal, questionnaire, and the new auto-added work-search follow-up (below) alike, whether the event was hand-added on the Calendar page or system-seeded. Built generic on purpose (Kyle's call) so it automatically covers Register's 26-week certification auto-seed and the follow-up feature with no special-casing
- [x] **Certification cutoff reminder.** `_send_certification_final_reminders()` fires separately at 5PM CT — 2 hours ahead of the 7PM CT IDES filing cutoff — for certification events landing today, over **email and SMS** (for claimants who've opted into SMS). Certification events are excluded from the generic 8AM "morning-of" reminder so this 5PM one is the one that actually lands close to the deadline, not a redundant earlier one
- [x] **5-business-day work-search follow-up.** `routers/contacts.py`'s `create_contact` now auto-adds a `calendar_events` entry (`event_type="other"`, no dedicated schema type needed) dated 5 business days after the contact is *logged* (today, not the possibly-back-dated `contact_date`), via a new `_add_business_days()` helper that skips weekends. Rides the same generic reminder engine above — no separate scheduling code needed, it just shows up as a normal event and gets the standard 3-day/morning-of reminder
- [x] **Reminder cadence + all reminders run regardless of subscription tier**, both per Kyle's call: 3-days-before + morning-of hardcoded (no per-claimant settings UI yet — can build one later if requested), and no tier gate on the reminder-sending jobs — consistent with the same reasoning already applied to Register's certification seeding (a compliance deadline or system-generated follow-up isn't the "manage your own calendar" paid feature that gates manual create/update)
- [x] Verified end-to-end via `TestClient` + mongomock: seeded certification events at +3 days and today, an IDES-interview event today; confirmed the 3-day scan fires exactly once (certification +3d), the morning scan fires exactly once and only for the non-certification event, and the cert-final scan fires exactly once with both an email AND an SMS recorded. Separately verified a real `POST /contacts` call auto-creates the follow-up event on the correct business-day-adjusted date
- [ ] **Not yet done:** files written directly into the local working tree, not yet committed/pushed. No live send has happened yet (Mailgun/ClickSend not exercised outside the mocked test) — first real firing will be the next scheduled 8AM/5PM CT tick after deploy

### Register Page — Branding, Validation & Certification-Date Seeding (Aug 20 — latest session)
Fixes the Register-page punch-list item above. Was also the unblock for the Calendar item (which needs a claimant's certification date to exist before it can build certification reminders on top of it — that data didn't exist anywhere in the app before this).
- [x] **Branding/disclaimer (was missing).** `Register.jsx` was a bare centered form with no product name and no IDES disclaimer anywhere — unlike `Login.jsx`, which already has a full left-side hero panel (brand bar, "Job Search Tracker" heading, "State of Illinois" label, and the "Unofficial tool — not affiliated with IDES" line). Rebuilt Register as the same two-column layout, reusing Login's exact copy/pattern rather than inventing new wording, so the two auth pages are now visually consistent
- [x] **Phone auto-format.** New `formatPhone()` masks input to `(XXX) XXX-XXXX` as the user types, stripping non-digits first so pasted numbers or a leading "1" don't break it
- [x] **Required-field marking**, front and back:
  - Frontend: red asterisks + `required` attributes on First/Last Name, Phone, DOB, Address, City, ZIP (Email/Password/Confirm Password already had `required`, asterisks added there too for consistency), plus a pre-submit check that toasts a specific "X is required" message and a `canSubmit` gate that disables the button until they're filled
  - Backend (`core.py`'s `RegisterIn`): these fields were previously all-optional — added `Field(min_length=1)` + a blank/whitespace-rejecting validator, since frontend-only validation doesn't stop a direct API call. **`invites.py`'s case-worker-invite flow doesn't use `RegisterIn`** (builds its own profile dict), so this doesn't affect that separate signup path
- [x] **"Do you know your next certification date?" Yes/No/N/A question**, added above Claimant ID. Answering "Yes" reveals a required date field; on submit, "yes" without a date is rejected both client-side (toast) and server-side (`RegisterIn` model-validator)
- [x] **26-week bi-weekly auto-seed.** New `core.py` helper `_seed_certification_events()` writes 26 `calendar_events` (14-day cadence, `event_type="certification"`) starting from the given date, called from `routers/auth.py`'s `/auth/register` right after the profile is created. Per Kyle's call, this runs for every new account regardless of subscription tier — `calendar_events` is otherwise a Pro/Case-Worker-gated feature (manually adding one goes through `gate_feature`), but a certification deadline is a compliance date, not the "manage your own calendar" premium feature, so it's seeded unconditionally rather than silently skipped for free-tier signups
- [x] Verified via a full FastAPI `TestClient` run against mongomock: blank required field → 422; `knows_next_cert_date=yes` with no date → 422; a valid registration seeds exactly 26 events at the correct 14-day cadence (spot-checked first/second/last dates) with a `CALENDAR_SEED` audit-log entry; `knows_next_cert_date=no` seeds nothing. Register.jsx's JSX syntax verified with an esbuild parse (no dev environment available to run the project's own ESLint here)
- [ ] **Not yet done:** files written directly into the local working tree, not yet committed/pushed. Calendar's actual reminder-sending engine (scanning these seeded events and firing email/SMS) is still separate, not-yet-built work — this task only builds the data + the Register-page UX

### ADJ034F Report Field-Population Fix (Aug 20 — latest session)
Fixes the ASAP "Week Detail" punch-list item above ("generated PDF only populates Last Name and ID/SSN, must populate every field every time"). All in `routers/reports.py`. Root cause was three separate bugs stacked in the same function:
- [x] **Wrong AcroForm field names (the main bug).** The fill code was writing to guessed field names ("weekend1", "date1", "name1", "address1", ...) that don't exist on the real form — pypdf silently no-ops on an unmatched field name instead of erroring, so almost everything rendered blank. "Last Name"/"ID or SSN" only ever worked by coincidence (those two guesses happened to match). Read the real field names directly off `assets/ADJ034F.pdf` via `PdfReader(...).get_fields()` (158 fields) and rewrote the mapping to match: 5 week-blocks ("Week Ending 1".."Week Ending 5"), each with 5 lettered contact rows a-e (25 rows total, not 30), and a single combined "Name and Address" field per row rather than separate name/address fields
- [x] **Dates never reformatted.** `_to_mmddyyyy()`'s `hasattr(value, "strftime")` check was dead code — `week_end`/`contact_date` are plain ISO strings per the Pydantic models, never datetime objects, so it never fired and dates landed on the form as raw "2026-08-08" text. Added a proper ISO-string parse path, falling back to the original string if parsing fails
- [x] **Middle Initial could never populate, and multi-word last names broke.** Old code built the name fields by concatenating first+last into one string and re-splitting it — `middle_initial` was never even included in what it split, so that field was dead no matter what was on file, and any multi-word last name (e.g. "Van Der Berg") got misattributed as an extra middle initial with the last name truncated. Now reads `first_name`/`last_name`/`middle_initial` directly off the profile document
- [x] Verified via a full FastAPI `TestClient` end-to-end test (multi-word last name + middle initial edge case) confirming every expected field lands correctly on the generated PDF; `py_compile`, full `server.py` import check, and `pyflakes` all clean
- [x] **Logo/disclaimer test-vs-code gap — resolved per Kyle's call.** `tests/test_round4.py::test_pdf_report_has_logo_and_unofficial` expected a reportlab-generated logo + "UNOFFICIAL" disclaimer that was never actually implemented in `reports.py` (reportlab isn't even a dependency anymore — see requirements.txt comment). Kyle chose not to build that overlay; the test was removed (with an explanatory comment left in its place) rather than left failing/skipped
- [x] **Added instead: a generation-timestamp stamp** along the bottom of every page of the generated PDF ("Generated by Illinois UI Job Tracker — MM/DD/YYYY HH:MM AM/PM UTC"), per Kyle's request. Implemented via a pypdf `FreeText` annotation (no reportlab needed) with the `/F=4` printable flag set so it survives printing, not just on-screen viewing. Verified: field values still fill correctly alongside the new annotation, annotation confirmed present on both pages after a full write/re-read round-trip
- [x] **Follow-up fix (below): "First Name" blank + claimant's first name leaking into the page-2 "Results 4d" box** — a second, deeper defect in the same template, found after Kyle reported it live. See "ADJ034F — First Name / Results 4d Field-Conflation Fix + Local Timestamp" below

### ADJ034F — First Name / Results 4d Field-Conflation Fix + Local Timestamp (Aug 20 — latest session)
Fixes two bugs Kyle found in the generated PDF after the fix above shipped: (1) "First Name" blank at the top of page 1, and (2) the claimant's first name printed into the 4th Results line of the middle contact group on page 2 (that box should hold the 19th contact's own result text). Also fixes a follow-up request to show the generation timestamp in local time instead of UTC. All in `routers/reports.py`.
- [x] **Root cause: a genuine authoring defect in the state's own `ADJ034F.pdf` template**, not a bug in our fill code. Dumped every "Results *" field's page + rect and found 4a/4b/4c/4e present but **4d entirely missing** from the form's field list — with the orphaned second widget of the "First Name" field landing exactly in that gap on page 2. In other words: the template's "First Name" field has **two widget annotations sharing one field identity** (the real box on page 1, plus a stray one on page 2 that should have been its own separate "Results 4d" field). Because both widgets share one field name, whatever value gets set for "First Name" is written to **both** locations — standard PDF behavior for a shared field name (like an SSN repeated on every page), just applied by mistake to two fields that are supposed to be independent. That's why the claimant's first name showed up in the page-2 Results box, and (per how pypdf resolves per-page appearance streams for a field split across pages) why the real First Name box on page 1 could end up rendering blank instead
- [x] **Fix:** new `_repair_adj034f_first_name_field(writer)`, run once against every generated PDF right after the template loads and before any fields are filled. It detaches the orphaned page-2 widget from "First Name"'s `/Kids` array, renames it to "Results 4d", and registers it as its own independent top-level AcroForm field — the existing fill logic already tries to write `field_values["Results 4d"]`, it just had nowhere valid to land before. Identifies the orphan by which page it actually renders on (not a hardcoded coordinate), so it stays correct if the template's layout ever shifts slightly. Safe to call unconditionally — a no-op if the template is ever fixed upstream
- [x] **Verified at three levels:** (1) an isolated test of the repair function alone, round-tripping two distinct values with no cross-contamination; (2) a no-19th-contact scenario confirming First Name populates and Results 4d stays correctly empty (no leakage when the slot isn't in use); (3) a full production-path end-to-end test — real `POST /auth/register` → real benefit week → 19 real contacts via `POST /contacts` (specifically enough to land contact #19 in section 4, letter "d", matching Kyle's exact "second page, middle group, 4th line" report) → real `GET /reports/benefit-week/{id}` → read the actual PDF back with pypdf. Confirmed: `First Name` = "Johnathan" (no longer blank), `Results 4d` = "Result-for-contact-19" (the contact's own result, not the claimant's name), `Name and Address 4d` = the contact's own employer/address, and the repaired "First Name" field has exactly 1 widget (`kids: 1`) after a full write/re-read round trip — confirming the detach stuck
- [x] **Timestamp switched from UTC to America/Chicago local time**, per Kyle's request — matches the timezone the rest of the app already runs on (scheduler, week bounds). Sample verified output: `08/20/2026 02:41 PM CDT` (correctly resolves the CDT/CST abbreviation via `%Z`, not hardcoded)
- [x] `routers/reports.py` delivered and committed to the device
- [ ] **Not yet done:** not yet committed to git / pushed

### Session Security / Auth Hardening (Aug 20 — latest session)
Fixes item 1 of the Site Fixes punch list above (ASAP: "app doesn't log the user out when they exit the browser or after a certain amount of time"). Root cause was four separate gaps, not one bug: the JWT lived in `localStorage` (survives closing the browser), had a flat 7-day expiry with no idle timeout, `AuthContext.jsx` only ever checked expiry once on mount (not while the tab stayed open), and `/auth/logout` never actually revoked anything server-side. Rebuilt as short-lived access tokens + rotating refresh tokens:
- [x] **Backend (`core.py`, `routers/auth.py`, `routers/invites.py`, `server.py`, `.env.example`)** — access-token JWT lifetime cut from 7 days to `ACCESS_TOKEN_MINUTES` (default 10). New `refresh_tokens` Mongo collection backs an opaque, rotating refresh token delivered as an httpOnly/Secure/SameSite=None cookie scoped to `/api/auth` — never readable by JS. `POST /auth/refresh` validates + rotates it (sliding `REFRESH_TOKEN_IDLE_MINUTES` expiry, default 30, hard-capped at `REFRESH_TOKEN_ABSOLUTE_HOURS` from the original login, default 12). Presenting an already-rotated-away token (a theft signal) revokes the entire session family immediately. `/auth/logout` now actually revokes the refresh token server-side instead of just writing an audit-log line. `refresh_tokens` added to the account-deletion purge list
- [x] **Frontend (`tokenStorage.js`, `api.js`, `AuthContext.jsx`, `WeekDetail.jsx`, `Documents.jsx`, `BenefitWeeks.jsx`)** — access token now lives only in a JS module variable (never in `localStorage`/`sessionStorage`), so it's gone the instant a tab closes and an XSS payload only ever gets a few minutes of it. `api.js` proactively refreshes an expiring token before a request goes out and silently retries once on 401. `AuthContext` re-establishes a session from the refresh cookie on page load (instead of reading a persisted token) and adds a 15-minute client-side idle timer as a UX backstop ahead of the backend's 30-minute window. The three pages that build raw `fetch()` downloads (PDF/CSV export, document upload/view) switched from `getToken()` to a new `getValidToken()` that refreshes first if needed, since they bypass the axios interceptor
- [x] **Removed the stale "Capacitor" comment** in `tokenStorage.js` — claimed `localStorage` was needed for a mobile (Capacitor) build; a full sweep of both `job-tracker` and `ijt-marketing` (deps, lockfiles, configs, source, docs, CI) found zero trace of Capacitor anywhere — no such build exists in either repo
- [x] **Real bug caught during testing:** `create_refresh_token()` crashed on every rotation (`TypeError: can't compare offset-naive and offset-aware datetimes`) — Mongo strips `tzinfo` off datetimes on round-trip (same class of issue this codebase already works around elsewhere, e.g. `_check_account_lockout`), so the rotated token's `family_started_at` came back naive and blew up comparing against the tz-aware idle expiry. Fixed by reattaching `tzinfo=utc` on read, same pattern as the rest of the file
- [x] Verified end-to-end: direct unit tests of rotation/reuse-detection/absolute-ceiling against an in-memory Mongo, plus a full FastAPI `TestClient` run of login → refresh → rotation → old-token-reuse-rejected-and-family-revoked → logout → refresh-after-logout-rejected. All 6 touched frontend files pass the project's ESLint config clean
- [x] **Committed and pushed** — confirmed on `origin/main` (commit `harden session auth, fix ADJ034F PDF, ship Register/Calendar/VerifyEmail`). ⚠ Also touches `.env.example` with 6 new optional session-security vars — see Environment Variables Checklist below for prod-specific notes (cross-site cookie between Vercel frontend and DigitalOcean backend needs `REFRESH_COOKIE_SECURE=true` + `REFRESH_COOKIE_SAMESITE=none`, which are already the defaults)
- [ ] **Separately flagged, not yet investigated:** `PROJECT_STATE.md`'s own Authentication & Security section (below) claims "single-active-session enforcement via session_id/sid JWT claim" — reading `core.py` directly, the JWT payload is only `{sub, email, exp, iat}` and `get_current_user()` does no session_id/sid check anywhere. This refresh-token rework does NOT add single-active-session enforcement either (each login gets its own independent refresh-token family; nothing stops two concurrent logins). Flagging the doc claim as inaccurate rather than quietly fixing/removing it — confirm with Kyle whether single-session enforcement was ever actually built, or was aspirational/planned and never shipped

### PWA Service Worker Was Serving a Stale, Pre-Session-Fix Bundle (Aug 20 — latest session)
Kyle reported that after the Session Security / Auth Hardening fix above shipped, he closed Chrome completely overnight, reopened it the next day, and was **still logged in** — seemingly proof the new 30-min-idle / 12h-absolute session logic wasn't working. Root cause was NOT the session logic (verified correct and live — see below), it was the frontend's PWA service worker serving an old cached bundle instead of ever loading the new one.
- [x] **Verified the new auth code actually was live** before looking anywhere else: confirmed `origin/main`'s HEAD matches the local repo's HEAD (both at commit `4ad268bf...`), and read the deployed `core.py`/`auth.py`/`AuthContext.jsx`/`tokenStorage.js`/`api.js` directly — the refresh-token idle/absolute expiry math, the tz-aware datetime comparisons, and the in-memory-only access token are all correct. This ruled out "the fix never shipped" and "the fix has a logic bug" as explanations
- [x] **Found the real cause: `vite.config.js`'s VitePWA config precached `html`** (`globPatterns: ["**/*.{js,css,html,woff2}"]`) with no override for navigation requests. Workbox's precache-and-route serves precached routes (including `/` → `/index.html`) straight from whatever was in the cache **at the service worker's install time** — a service worker installed in Kyle's browser any time before this fix shipped keeps serving that old HTML+JS pair indefinitely, regardless of what's actually deployed, until that specific service worker instance happens to get replaced through its own update cycle. The old bundle it served still used the pre-Aug-20 approach (JWT saved to `localStorage`, 7-day expiry) — so a fully-closed-and-reopened Chrome could load the stale service worker's cached old bundle, find the old still-unexpired `localStorage` token, and render "logged in," without the new session code ever running
- [x] **Fix (`vite.config.js`):** dropped `html` from `globPatterns` (JS/CSS/fonts stay precached — those are content-hashed by Vite, so a stale cached asset is never served under a URL a new deploy would reuse), added `navigateFallback: null`, and added a `NetworkFirst` runtime-caching rule for navigation requests (3s network timeout, falling back to the last-cached shell only if the network is truly unreachable). Every visit now fetches the current `index.html` — and therefore whichever JS bundle is actually deployed — from the network first
- [x] Verified `node --check` passes on the updated config (no `node_modules` available in this environment to run a full `vite build`)
- [ ] **Not yet done:** file delivered and written to the local working tree; not yet committed/pushed. Kyle's own browser will pick up the fix on its own once the new service worker activates there (one extra background reload), but a hard refresh (Ctrl+Shift+R) or DevTools → Application → Service Workers → Unregister will clear the stale one immediately if needed sooner
- [ ] **Not investigated:** whether any other returning users hit the same stale-session illusion between when the session-hardening fix shipped and when this PWA fix ships — no way to detect that after the fact from the app's current logging

### Design/Quality Pass, Dark-Mode Fix & Repo Hygiene (Aug 20)
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
- [x] Single-active-session enforcement via session_id/sid JWT claim ⚠ **Aug 20: could not confirm this in the code.** `core.py`'s JWT payload is only `{sub, email, exp, iat}` — no `sid`/`session_id` claim, and `get_current_user()` does no such check. May be stale/aspirational — confirm with Kyle whether this was ever actually built
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
| ACCESS_TOKEN_MINUTES | New (Aug 20), optional — access-token JWT lifetime, default 10 |
| REFRESH_TOKEN_IDLE_MINUTES | New (Aug 20), optional — refresh-token sliding expiry, default 30 |
| REFRESH_TOKEN_ABSOLUTE_HOURS | New (Aug 20), optional — hard session ceiling from original login, default 12 |
| REFRESH_COOKIE_SECURE | New (Aug 20), optional, default `true` — must stay `true` in prod (HTTPS) |
| REFRESH_COOKIE_SAMESITE | New (Aug 20), optional, default `none` — required as-is since frontend (Vercel) and backend (DigitalOcean) are different domains; a same-site value would silently break refresh in prod |
| REFRESH_COOKIE_DOMAIN | New (Aug 20), optional, default blank — leave unset unless frontend/backend ever share a parent domain |

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
| core.py | Shared app state, models, helpers. `send_sms()` migrated to ClickSend's REST API (Aug 19-20); `RegisterIn`/`Profile` models gained `sms_opt_in` / `sms_opt_in_at`. Updated (Aug 20) — access-token lifetime cut to 10 min; new refresh-token issue/rotate/revoke helpers backed by a new `refresh_tokens` collection |
| routers/sms.py | OTP send/verify endpoints — Twilio-trial error message rewritten for ClickSend (Aug 19-20) |
| routers/auth.py | Registration handler — now seeds SMS opt-in consent (`sms_enabled`, `sms_opt_in_at`, `SMS_OPT_IN` audit log entry) from the Register-page checkbox (Aug 19-20). Updated (Aug 20) — `/auth/login` and the new `/auth/refresh` issue/rotate the refresh cookie; `/auth/logout` now revokes it server-side |
| routers/invites.py | Updated (Aug 20) — `/invite/redeem` now also issues a refresh-token cookie on account creation (previously only returned a bare access token with no way to refresh it) |
| core.py — `RegisterIn` model | Updated (Aug 20) — first_name/last_name/phone/dob/address/city/zip now required (`Field(min_length=1)` + blank-rejecting validator); new `knows_next_cert_date`/`next_certification_date` fields with a model-validator requiring the date when "yes" |
| core.py — `_seed_certification_events()` | New (Aug 20) — writes 26 bi-weekly `calendar_events` (14-day cadence) from a given start date; called from `/auth/register`, runs regardless of subscription tier |
| routers/auth.py — `/auth/register` | Updated (Aug 20) — calls `_seed_certification_events()` when `knows_next_cert_date == "yes"`, logs a `CALENDAR_SEED` audit entry |
| core.py — "Calendar Event Reminders" section | New (Aug 20) — `_broadcast_event_reminders()`, `_send_certification_final_reminders()`, `_due_calendar_events()`, `_add_business_days()`, `EVENT_TYPE_LABELS` — the Calendar reminder engine |
| server.py — scheduler | Updated (Aug 20) — 3 new jobs: `cal_3day`/`cal_morning` (daily 8AM CT) and `cal_cert_5pm` (daily 5PM CT), alongside the existing purge/weekly-reminder jobs |
| routers/contacts.py — `create_contact` | Updated (Aug 20) — auto-adds a 5-business-day follow-up `calendar_events` entry after logging a contact |
| assets/ADJ034F.pdf | Present on disk (confirmed Aug 20; doc previously claimed it was missing — see Known Bugs) |
| routers/reports.py | Updated (Aug 20) — fixed the ADJ034F field-population bug: real AcroForm field names (were guessed/wrong), proper ISO-to-US date formatting (was dead code), Middle Initial + multi-word last names read directly from the profile instead of a broken concatenate-and-resplit; also now stamps a generation timestamp along the bottom of every page via a pypdf FreeText annotation |
| tests/test_round4.py | Updated (Aug 20) — removed `test_pdf_report_has_logo_and_unofficial` (expected a reportlab logo/disclaimer overlay that was never built and isn't planned; Kyle's call) |
| requirements.txt | Python dependencies — `twilio` removed Aug 19-20 (ClickSend goes over the existing `requests` dependency) |
| Dockerfile | Container definition |

### Frontend — Main App (APP/frontend/src/)
| File | Purpose |
|---|---|
| pages/WeekDetail.jsx | Benefit week + contacts, loading/error states. Updated (Aug 20) — PDF/CSV download now calls `getValidToken()` instead of the old `getToken()` so a stale in-memory access token refreshes first. Also where the ADJ034F report bug's endpoint (`GET /reports/benefit-week/{id}`) was traced to — see In Progress |
| pages/Documents.jsx, pages/BenefitWeeks.jsx | Updated (Aug 20) — same `getValidToken()` swap as WeekDetail.jsx, for their raw-`fetch()` upload/download/export calls |
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
| context/AuthContext.jsx | Auth state. Updated (Aug 20) — was checking a persisted `sessionStorage`-described-but-actually-`localStorage` token once on mount; now re-establishes session via `refreshSession()` (httpOnly cookie) on load and adds a 15-min client-side idle logout timer |
| lib/api.js | Axios client + JWT interceptor. Updated (Aug 20) — `withCredentials: true`, proactive refresh-before-expiry, silent refresh-and-retry-once on 401, exports `refreshSession()`/`getValidToken()` |
| lib/tokenStorage.js | Updated (Aug 20) — access token moved from `localStorage` (survived closing the browser, readable by any script for its full life) to an in-memory JS variable only; also removes a stale comment claiming it was needed for a "Capacitor" mobile build that doesn't exist anywhere in this repo |
| pages/Register.jsx | Updated (Aug 19-20) — added unchecked-by-default SMS opt-in checkbox below the phone field, for ClickSend toll-free compliance |
| pages/Profile.jsx | Updated (Aug 19-20) — SMS card now carries full opt-in disclosure (brand name, frequency, rates, STOP/HELP, Terms/Privacy links) around the existing SMS toggle |
| pages/PrivacyPolicy.jsx, pages/Terms.jsx | Updated (Aug 19-20) — SMS sections rewritten for ClickSend (Data Collection/Usage/Sharing/Opt-Out); "⚠ ATTORNEY REVIEW REQUIRED" header comment removed |
| pages/Admin.jsx | Updated (Aug 19-20) — Integrations tab SMS provider card changed from hardcoded "Twilio" to "ClickSend" |
| pages/Landing.jsx | Updated (Aug 19-20) — feature-grid copy "Mailgun + Twilio" → "Mailgun + ClickSend" |
| pages/Register.jsx | Updated (Aug 20) — two-column branding/disclaimer layout matching Login.jsx, phone auto-format, required-field marking, and the new "next certification date" Yes/No/N/A question with conditional date field |
| pages/VerifyEmail.jsx | Updated (Aug 20) — branded "IL" badge header (matches the reminder-email header style) + IDES disclaimer footer added; error/spinner states polished |

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
| ADJ034F.pdf missing from assets/ | Doc error, corrected (Aug 20) | This file was always present on disk (1.5MB, confirmed via `PdfReader` reading its 158 AcroForm fields) — the "missing" claim in this doc was stale/inaccurate |
| ADJ034F report only populated Last Name and ID/SSN | Fixed (Aug 20, not yet deployed) | Wrong AcroForm field names (guessed, didn't match the real form except by coincidence), dead date-reformat code, and a broken middle-initial/name-derivation path — all three fixed in `routers/reports.py`. See "ADJ034F Report Field-Population Fix" under Completed |
| `test_pdf_report_has_logo_and_unofficial` expected a logo/"UNOFFICIAL" overlay that doesn't exist in the code | Fixed (Aug 20) | Pre-existing gap, found while fixing the field-mapping bug. Kyle chose not to build the reportlab logo/disclaimer overlay — test removed, and a lightweight generation-timestamp stamp added to the PDF instead (see "ADJ034F Report Field-Population Fix" under Completed) |
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
| App doesn't log the user out on browser close or after time elapses | Fixed (Aug 20, not yet deployed) | 7-day `localStorage` JWT with no idle timeout and no server-side logout revocation. Rebuilt as a 10-min in-memory access token + rotating httpOnly-cookie refresh token (30-min idle / 12-hr absolute ceiling), real server-side revocation on logout, and a 15-min client-side idle timer. See "Session Security / Auth Hardening" under Completed |
| `create_refresh_token()` crashed on every rotation (naive/aware datetime TypeError) | Fixed (Aug 20, caught in testing, never shipped) | Mongo strips `tzinfo` off datetimes on round-trip; `family_started_at` came back naive and blew up comparing against a tz-aware expiry. Reattached `tzinfo=utc` on read, matching the pattern already used elsewhere in `core.py` |
| `PROJECT_STATE.md` claims single-active-session enforcement (session_id/sid JWT claim) that isn't in the code | Open — needs Kyle to confirm | `core.py`'s JWT payload has no `sid`/`session_id` field and `get_current_user()` doesn't check one. Not added by the Aug 20 refresh-token work either — multiple concurrent logins are currently unrestricted |

---

## How To Update This File

After completing any item:
1. Move it from **Pending** or **In Progress** to **Completed** with a `[x]`
2. Update **Last Updated** date at the top
3. Add any new open items or bugs discovered
4. Commit: `git commit -m "Update PROJECT_STATE.md"`

This file lives at the root of the `job-tracker` repo. Push it after every session.
