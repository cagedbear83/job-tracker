# Clerk Migration Plan — Illinois UI Job Tracker

Status: **proposal for approval — no code changed yet.**
Author: prepared from the current codebase (`APP/frontend` React+Vite, `APP/backend` FastAPI).

---

## 1. The core idea

Your app already has one thing going for it that makes this safe: **every
protected backend route flows through a single function, `get_current_user`
in `app/security.py`.** And **all domain data (profiles, benefit weeks,
contacts, audit log, invites) is keyed to `users.id`** — a UUID your app
controls, not the auth provider.

So the strategy is:

- **Keep `users.id` as the permanent primary key.** Nothing about your data
  linkage changes.
- **Clerk becomes the identity/credential provider only.** It owns sign-up,
  sign-in, password reset, email verification, and the user profile UI.
- **Link the two by adding one field, `clerk_user_id`, to each user doc.**
- **Keep authorization (the `role` field) in your own database.** `require_admin`
  keeps working unchanged.

The result: `get_current_user` is the main backend rewrite. The other ~53
routes don't change, because they still receive the same user dict shape.

---

## 2. What changes, by layer

### Frontend (`APP/frontend`)

| File | Change |
|---|---|
| `src/main.jsx` | `ClerkProvider` already added by `clerk init`. Keep it; optionally make `publishableKey` explicit. |
| `src/context/AuthContext.jsx` | **Rewrite internals, keep the same shape.** Identity (`user`, signed-in state) now comes from Clerk (`useUser`, `useAuth().getToken`) instead of `/auth/login` + localStorage. Keep exposing `user`, `claimants`, `activeClaimantId`, `setActiveClaimant`, `role` so **Layout and all pages keep using `useAuth()` unchanged.** `role`/`name`/`active_claimant_id` still come from a `GET /auth/me` call once the Clerk session exists. |
| `src/lib/api.js` | Axios request interceptor attaches the **Clerk session token** via `getToken()` (async) instead of reading `tokenStorage`. |
| `src/lib/tokenStorage.js` | Removed — Clerk manages the session. |
| `src/App.jsx` | `/login` → Clerk `<SignIn/>`; `/register` → `<SignUp/>`. `Protected` uses Clerk `<SignedIn>/<SignedOut>` (or `useAuth().isSignedIn`). `/forgot-password`, `/reset-password`, `/verify-email` routes removed (Clerk owns these). |
| `src/components/Layout.jsx` | Replace the custom name/email + Logout button with `<UserButton/>`. **Keep the claimant switcher and admin nav** (still driven by `role` from `/auth/me`). |
| `src/pages/Login.jsx`, `Register.jsx`, `ForgotPassword.jsx`, `ResetPassword.jsx`, `VerifyEmail.jsx` | Retired (replaced by Clerk components). Files can be deleted in the cleanup phase. |
| `@clerk/ui` (Step 8) | Optional polish: apply the shadcn theme so Clerk widgets match your existing UI (`components.json` is present). |
| `.env` | Keep `VITE_CLERK_PUBLISHABLE_KEY`. **Move `CLERK_SECRET_KEY` out of the frontend `.env`** — it belongs to the backend only. |

### Backend (`APP/backend`)

| File | Change |
|---|---|
| `app/security.py` → `get_current_user` | **The main change.** Verify a Clerk session JWT (RS256, validated against Clerk's JWKS / issuer) instead of the current HS256 token. Read `sub` = Clerk user id, look up `db.users` by `clerk_user_id`; if absent, link by email (or auto-provision). Return the **same user dict** the routes already expect. |
| `app/security.py` (rest) | `hash_password`, `verify_password`, `validate_password_policy`, account-lockout helpers, `create_token` → removed (Clerk owns credentials). |
| `app/routers/auth.py` | `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/verify-email`, `/auth/logout` → removed or return `410 Gone`. **Keep `GET /auth/me`** (frontend needs role/name/active claimant). |
| `app/config.py` | Drop password-policy, lockout, and login rate-limit constants. Add Clerk config (issuer / JWKS URL, `CLERK_SECRET_KEY`). |
| `app/main.py` (startup) | Remove password-based demo/admin seeding. Seed the admin instead by email + `role="admin"` on the local doc, linked to Clerk on first sign-in. |
| `app/routers/invites.py` | Decide invites approach (see §4). |
| `requirements.txt` | Add `clerk-backend-api` (official) **or** rely on `PyJWT` + JWKS. `bcrypt`/`PyJWT` stay only if the password-import path is used. |
| `.env` | Add `CLERK_SECRET_KEY` and the Clerk issuer. Remove `JWT_SECRET` once the legacy path is gone. |
| `require_admin` | **Unchanged** — still reads `user["role"]`. |
| The other ~53 routes | **Unchanged.** |

### Database

- Add `clerk_user_id` (nullable) to `users`, with a unique **sparse** index.
- `users` stays the source of truth for `role` and all domain linkage.
- Collections that only existed for the old auth (`login_attempts`,
  `password_resets`) become unused and can be dropped after cutover.

---

## 3. Migrating existing users (the real decision)

Existing accounts have `email` + a bcrypt `password_hash`. Two ways to bring
them into Clerk:

**Option A — Password-preserving import (best UX).**
One-time script exports `(email, password_hash)` and imports each into Clerk
via the Backend API using `password_digest` (Clerk supports bcrypt). Store the
returned Clerk id as `clerk_user_id`. **Users keep their existing passwords;
no reset.** Requires a Clerk plan/feature that allows password-hash import.

**Option B — Self-service re-onboard (simplest).**
Users sign up in Clerk with the same email; on their first authenticated
request the backend links by email to the existing `users` doc and stamps
`clerk_user_id`. **Users set a new password (or use Google/OAuth).** No import
script, but everyone re-establishes credentials once.

Either way, **all their data stays intact** because linkage is by email → the
existing `users.id`, which never changes.

---

## 4. Open decisions to lock before coding

1. **Password migration:** Option A (import hashes, no reset) vs Option B
   (re-onboard). Affects whether we write an import script and keep bcrypt.
2. **Invites** (`/admin/invites`, `/invite/redeem`): (a) switch to Clerk
   invitations, (b) keep the custom invite that also creates a Clerk
   invitation, or (c) defer — freeze invites until after cutover.
3. **Email in the token:** to link by email we either add a Clerk **JWT
   template** that includes `email` (no extra call per request) or fetch the
   user from Clerk's API at link time. Recommendation: JWT template.
4. **Backend tests:** `tests/*.py` currently authenticate via `/auth/login`,
   which goes away. They'll be rewritten to use Clerk testing tokens
   (the `clerk-testing` skill covers this).
5. **PII/compliance sign-off:** identity data (emails, auth) now lives in
   Clerk. Worth a final confirmation given this is claimant data.

---

## 5. Suggested sequencing (incremental, low-risk)

- **Phase 0 — done.** CLI init, SDK installed, `ClerkProvider` mounted.
- **Phase 1 — backend, additive (no breakage).** Add `clerk_user_id` + index.
  Make `get_current_user` accept **both** the legacy HS256 token **and** a
  Clerk token (dual-auth). This lets the frontend flip without a hard cutover.
- **Phase 2 — frontend swap.** `<SignIn>/<SignUp>` routes, Clerk token in
  `api.js`, `<UserButton>` in Layout, keep `/auth/me`. Validate by signing in
  as your first Clerk user (auto-linked/provisioned).
- **Phase 3 — user migration.** Run Option A import, or announce Option B
  re-onboarding. Confirm your admin account links with `role="admin"`.
- **Phase 4 — remove legacy.** Delete password/lockout/reset code and dead
  pages, drop the HS256 path and `JWT_SECRET`, clean `config.py`, retire
  `login_attempts`/`password_resets`.
- **Phase 5 — verify.** Rewrite backend tests for Clerk; run frontend
  sign-in/up/out; `clerk doctor`; confirm all 54 routes still authorize.

Phases 1–2 are reversible and don't disturb current users. The point of no
return is Phase 4.

---

## 6. What stays exactly the same

- All 54 API routes and their paths.
- The `app/` package structure from the refactor.
- `users.id` and every collection keyed to it (no data re-keying).
- `role`-based authorization and `require_admin`.
- The claimant switcher, admin nav, and app pages.
