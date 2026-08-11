# Security Review — diff `71a6bbf..HEAD`

Scope: CI workflow, deploy configs (`render.yaml`), env examples, MongoDB
client tuning, and the staging/production rollout commits. Excludes the
unrelated `.tmp.driveupload/*` deletions and pure frontend UI/loading-state
changes (`WeekDetail.jsx`, `dateUtils.js`), which carry no security-relevant
logic in this diff.

## Findings

### 1. MEDIUM — Staging environment disables brute-force protection on auth endpoints while shipping known demo credentials
**File:** [render.yaml](render.yaml)

```yaml
  # ---------------- Staging ----------------
  - type: web
    name: ides-job-tracker-api-staging
    ...
    envVars:
      ...
      - key: ENABLE_DEMO_USER
        value: "true"
      - key: RATE_LIMIT_ENABLED
        value: "false"
```

**Issue:** This commit adds a second, publicly-deployable Render web service
(`branch: staging`) and explicitly sets `RATE_LIMIT_ENABLED=false` (comment:
"rate limits off for QA"). `RATE_LIMIT_ENABLED` gates the limiter applied to
`/login`, `/register`, and `/forgot-password` in [server.py:106-129](APP/backend/server.py#L106-L129)
and [server.py:567](APP/backend/server.py#L567) (`@rate_limit(RATE_LIMIT_LOGIN)`),
[server.py:498](APP/backend/server.py#L498) (register), and
[server.py:1311](APP/backend/server.py#L1311) (forgot-password). With it off,
these endpoints have no throttling on a network-reachable host.

Compounding this, the same block sets `ENABLE_DEMO_USER=true` without
overriding `DEMO_USER_EMAIL`/`DEMO_USER_PASSWORD`, so the seeded account uses
the hardcoded defaults in [server.py:2187-2188](APP/backend/server.py#L2187-L2188)
(`demo@illinoistracker.test` / `Demo1234!`) — credentials visible to anyone
reading this public repo.

**Attack path:** An attacker who finds the staging URL (Render subdomains are
guessable/discoverable, and `autoDeploy: true` + `branch: staging` means it's
live continuously) can:
- Log in immediately with the known demo credentials, or
- Run unthrottled credential-stuffing/brute-force against `/login` for any
  other account that exists on staging (including a configured
  `ADMIN_EMAIL`/`ADMIN_PASSWORD` admin account, since staging shares the same
  app code path), or
- Hammer `/forgot-password` to enumerate registered emails or exhaust
  Mailgun/Twilio send quotas (`sync: false` staging creds for Mailgun/Twilio
  are wired into this same service).

**Why existing controls don't block it:** the rate limiter exists and
defaults to "on" everywhere else (`RATE_LIMIT_ENABLED` default `"true"` at
[server.py:106](APP/backend/server.py#L106)); this PR is the one place that
flips it off for a real, deployed, network-facing service rather than a local
test run.

**Recommendation:** Don't disable rate limiting on any deployed environment.
If QA needs higher limits, raise the threshold via a dedicated env var
instead of an on/off switch, and put staging behind basic auth / IP allowlist
if demo credentials must stay enabled.

**Status: FIXED.** `render.yaml` staging now sets `RATE_LIMIT_ENABLED: "true"`,
matching production, with a comment pointing at the per-endpoint
`RATE_LIMIT_*` env vars for QA throughput instead of disabling the limiter.

---

## Findings from a second automation pass (Cursor), validated and fixed

A separate Cursor-run review against commit `27a9e37` surfaced four more
findings. All four were re-verified line-by-line against the current
codebase before fixing (all were still live, none had been previously
addressed):

### 2. HIGH — Registration returned a session token before email verification (account pre-hijacking)
**File:** [server.py](APP/backend/server.py)

`POST /auth/register` set `email_verified: False` but still returned
`create_token(uid, email)`, and `get_current_user` never checked
`email_verified` — only `/auth/login` did. An attacker could register a
victim's email, immediately use the returned token against every
authenticated endpoint, and the account would later flip to "verified" the
moment the real victim clicked the legitimate verification email — at which
point the attacker still holds the password.

**Status: FIXED.** `register()` no longer issues a token; it returns a
`message` + `user` only (new `RegisterOut` model). A session can only be
obtained via `/auth/login`, which already rejects unverified accounts. Updated
`AuthContext.register()` on the frontend to match (it no longer calls
`setToken`/`setUser` after registration — `Register.jsx` already redirected to
`/login` afterward, so no UX change). As defense in depth, `_send_user_reminder`
now also short-circuits for any non-verified account.

### 3. HIGH — Client-writable `sms_verified`/`reminder_email` allowed sending app-branded email/SMS to arbitrary recipients
**File:** [server.py](APP/backend/server.py), [Claimants.jsx](APP/frontend/src/pages/Claimants.jsx)

`ProfileIn.sms_verified` and `sms_phone` were plain client-writable fields,
and `upsert_profile`/`create_claimant`/`update_claimant` persisted
`body.model_dump()` verbatim — so a client could mark any phone number
"verified" without ever proving ownership via the real OTP flow
(`/sms/send-otp` + `/sms/verify-otp`). `_send_user_reminder` then sent SMS
whenever `sms_enabled && sms_phone && sms_verified` were all true, with no
re-check against the OTP record. Reminder emails also interpolated
user-controlled name/employer/contact fields into HTML via unescaped
f-strings, and `reminder_email` (also client-writable) controlled the actual
recipient.

Worse: the frontend's "new claimant" form ([Claimants.jsx](APP/frontend/src/pages/Claimants.jsx))
shipped with **hardcoded defaults of `sms_phone: "+14423321758"` and
`sms_verified: true`** baked into every new claimant created through the
normal UI — meaning this wasn't just a theoretical API-level bypass, ordinary
use of the app would silently start sending SMS reminders to a real-looking
phone number that doesn't belong to the user, unless they noticed and
cleared the field.

**Status: FIXED.**
- `sms_phone`/`sms_verified` removed from `ProfileIn` (client input) and
  moved to `Profile` (response-only) — they can now only be set by
  `/sms/verify-otp` after a real one-time code is confirmed.
- Reminder email bodies now `html.escape()` all user-controlled
  interpolations (name, employer, position, date) before building the HTML.
- `/reminders/test` is now rate-limited (`RATE_LIMIT_REMINDER_TEST`,
  default `10/hour`).
- `_send_user_reminder` refuses to send for unverified accounts (see above).
- Removed the dangerous hardcoded `sms_phone`/`sms_verified: true` defaults
  from the "new claimant" form; the SMS phone number text field was removed
  from the main edit dialog entirely (it had no effect once the backend
  stopped trusting client-submitted values) in favor of the existing
  "Verify phone" OTP flow.

### 4. HIGH — Mailgun API key logged on every outbound email
**File:** [server.py](APP/backend/server.py)

`send_email()` unconditionally logged
`f"MAILGUN DEBUG key={os.environ.get('MAILGUN_API_KEY', ...)}"` on every call,
hit by both public registration and forgot-password. The same
`MAILGUN_API_KEY` doubles as the HMAC secret for verifying inbound Mailgun
webhook signatures, so a leaked key also lets an attacker forge webhook
events.

**Status: FIXED.** Removed the debug log line entirely. **Note:** if this key
has ever been deployed with logging enabled, rotate it in the Mailgun
dashboard — removing the log line does not invalidate a key that may already
be sitting in historical log output.

### 5. MEDIUM — Unbounded CSV/screenshot import endpoints (resource & API-cost amplification)
**File:** [server.py](APP/backend/server.py)

`/import/csv` read the entire upload into memory and inserted every row with
no size or row cap. `/import/screenshot` read the entire upload, base64-
encoded it, and forwarded it to Gemini with no size, MIME, or
dimension check — any authenticated user could submit an oversized file to
exhaust memory/DB storage or run up Gemini API costs.

**Status: FIXED.**
- `/import/csv`: rejects files over `MAX_CSV_IMPORT_BYTES` (2 MB default,
  413), caps processed rows at `MAX_CSV_IMPORT_ROWS` (500 default).
- `/import/screenshot`: rejects files over `MAX_SCREENSHOT_IMPORT_BYTES`
  (8 MB default, 413), enforces a MIME allowlist (PNG/JPEG/WEBP), and
  decodes the image up front (`pil_image.load()`) so malformed or
  decompression-bomb-style images fail fast with a 400 instead of reaching
  Gemini — plus an explicit `MAX_SCREENSHOT_PIXELS` (~25MP) cap.
- All four limits are env-overridable for deployments that need more
  headroom.

---

## Notes / non-findings
- `JWT_SECRET: generateValue: true` for both services — fine, not reused.
- `ci.yml`'s hardcoded `JWT_SECRET`/`DEMO_USER_PASSWORD` are scoped to an
  ephemeral, localhost-only Mongo container in GitHub Actions — not a secret
  leak.
- `.dockerignore` correctly excludes `.env*` (except `.env.example`); no real
  `.env` is tracked in git.
- The various committed `*.html` docs (`index.html`, `docs/DEPLOYMENT.html`,
  `APP/memory/PRD.html`, `APP/test_result.html`) only contain placeholder
  values (`<your-mailgun-api-key>`, etc.), not real secrets.
- MongoDB client pooling/timeout changes in `server.py` are operational
  tuning only, no new attack surface.
- `WeekDetail.jsx` / `dateUtils.js` changes are UI loading-state and
  dropdown additions — no new injection, authz, or rendering risk (no
  `dangerouslySetInnerHTML`, no new fetch targets, server URL untouched).

## Outcome
**5 findings total (3 high, 2 medium) across both review passes — all fixed.**
No high-confidence vulnerabilities remain open as of this commit.

## Not in scope / follow-ups not addressed
- Email enumeration via `409`-style "Email already registered" response on
  `/auth/register` was not flagged by either review pass and was left as-is.
- If `MAILGUN_API_KEY` has ever been deployed with the now-removed debug log
  active, it should be rotated — code fixes don't scrub historical logs.
