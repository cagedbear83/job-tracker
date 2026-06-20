# Deployment & Environments

This guide sets up **MongoDB Atlas** plus separate **staging** and **production**
environments for the backend (Render) and frontend (Vercel).

## Environment overview

| Concern            | Staging                          | Production                        |
| ------------------ | -------------------------------- | --------------------------------- |
| Git branch         | `staging`                        | `main`                            |
| Backend (Render)   | `ides-job-tracker-api-staging`   | `ides-job-tracker-api`            |
| Database (Atlas)   | `ides_tracker_staging`           | `ides_tracker_prod`               |
| Demo user          | enabled                          | disabled                          |
| Rate limiting      | off (for QA)                     | on                                |
| Integrations       | sandbox/test credentials         | live credentials                  |

Promotion flow: merge work to `staging` → verify on the staging URLs → open a
PR from `staging` to `main` → merge to ship to production.

---

## 1. MongoDB Atlas

1. Create a free account at <https://www.mongodb.com/atlas> and a new **Project**
   (e.g. `illinois-job-tracker`).
2. **Create a cluster.** An `M0` (free) cluster is fine to start; move to `M10+`
   for production backups and better performance when you have real users.
   - Strongest isolation: one cluster for staging, one for production.
   - Cheapest acceptable: a single cluster with two **databases**
     (`ides_tracker_staging` and `ides_tracker_prod`). This Blueprint assumes
     the two-database approach but works either way — it only depends on
     `MONGO_URL` + `DB_NAME` per environment.
3. **Database user:** Atlas → *Database Access* → add a user with a strong
   password and the `readWrite` role on the relevant database(s).
4. **Network access:** Atlas → *Network Access* → add the egress IPs of your
   Render services. For an initial setup you may temporarily allow `0.0.0.0/0`,
   but lock this down to Render's static outbound IPs before launch.
5. **Connection string:** Atlas → *Connect* → *Drivers* → copy the SRV string:
   ```
   mongodb+srv://USER:PASS@cluster0.xxxx.mongodb.net/?retryWrites=true&w=majority
   ```
   Use this as `MONGO_URL`. Do **not** put the database name in the URL — it is
   provided separately via `DB_NAME`.
6. **Backups (production):** on `M10+`, enable continuous/cloud backups and run
   one test restore so you know the recovery path works.

The backend tunes its Atlas connection via these env vars (defaults shown);
they rarely need changing at launch:

```
MONGO_APP_NAME=ides-job-tracker
MONGO_MAX_POOL_SIZE=20            # one worker, low concurrency
MONGO_MIN_POOL_SIZE=0            # no idle connections on small tiers
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000   # fail fast -> /health/ready returns 503 quickly
MONGO_CONNECT_TIMEOUT_MS=10000
```

---

## 2. Backend → Render (Docker)

The repo ships `render.yaml`, a Blueprint defining **both** services.

1. Push a `staging` branch (production deploys from `main`):
   ```bash
   git checkout main && git pull
   git checkout -b staging && git push -u origin staging
   ```
2. Render dashboard → *New* → *Blueprint* → pick this repo. Render reads
   `render.yaml` and proposes the two web services.
3. For **each** service, fill in the `sync: false` secrets:
   - `MONGO_URL` — the Atlas SRV string (staging and prod can differ).
   - `FRONTEND_URL` — that environment's frontend URL (used for verification /
     reset / invite links and CORS).
   - `CORS_ORIGINS` — the exact frontend origin(s), comma-separated. **Never use
     `*` in production.**
   - Optional: `SENTRY_DSN`, Mailgun/Twilio/Gemini keys (use sandbox creds for
     staging).
   - `JWT_SECRET` is auto-generated per service; `DB_NAME` is preset.
4. Deploy. Render runs the container's `HEALTHCHECK` and routes the
   `healthCheckPath` (`/health/ready`) so traffic only flows once Mongo is
   reachable.

> Keep `WEB_CONCURRENCY=1` for now: the reminder scheduler (APScheduler) runs
> in-process, so multiple workers would duplicate cron jobs. Splitting the
> scheduler into its own worker is the prerequisite for scaling out.

---

## 3. Frontend → Vercel

1. Vercel → *Add New Project* → import this repo.
2. **Root Directory:** `APP/frontend` (so Vercel builds the React app, not the
   repo root). `vercel.json` handles the SPA rewrite, security headers, and
   asset caching.
3. **Environment variables** (Project → Settings → Environment Variables):
   - `REACT_APP_BACKEND_URL`
     - *Production* → your production Render URL (e.g.
       `https://ides-job-tracker-api.onrender.com`)
     - *Preview* → your staging Render URL
   - Optional: `REACT_APP_SENTRY_DSN`, `REACT_APP_SENTRY_ENVIRONMENT`.
4. Production deploys from `main`; Preview deployments are created per branch/PR
   (point these at the staging backend). For a stable staging URL, you can also
   assign a domain alias to the `staging` branch deployment.

After both sides are up, set each backend's `CORS_ORIGINS` to the matching
frontend origin and redeploy.

---

## 4. Smoke test a deploy

```bash
# Liveness + readiness (readiness pings MongoDB)
curl -fsS https://<backend-host>/health/live
curl -fsS https://<backend-host>/health/ready

# App boots and talks to the API
open https://<frontend-host>
```

A `503` from `/health/ready` means the backend is up but cannot reach MongoDB —
check `MONGO_URL`, the Atlas database user, and the Network Access allowlist.
