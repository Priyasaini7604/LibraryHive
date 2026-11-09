# LibraryHive: production deployment guide

**Status:** prepared, **not deployed**. Nothing in this file has been run against a hosted service. Every step that creates a service, changes a secret, runs a migration, publishes code or enables a schedule needs the project lead's approval first.

Target: **Vercel** (frontend), **Render** (backend web service), **Neon** (PostgreSQL), **GitHub Actions** (scheduled jobs), **S3-compatible object storage** (two buckets). Variable names below are the ones the code reads (`backend/config/settings/*.py`, `frontend/next.config.ts`, `frontend/proxy.ts`, `frontend/lib/*.ts`); no secret value belongs in this repository.

Facts about Render in this guide come from Render's own documentation (see the links in section 3). Anything marked **verify** was not confirmed and must be checked in the Render dashboard before you rely on it.

---

## 1. Blockers to settle before going live

| # | Blocker | Why |
|---|---|---|
| 1 | **Private object storage must exist and be tested.** Create two buckets (public photos, private payment images) and run section 6 against the real provider. | The UPI QR codes and payment screenshots live in the private store. Render's disk is ephemeral, so the app **refuses to start** with `ENVIRONMENT=production` unless `STORAGE_BACKEND=s3`, both bucket names and both keys are set, and the private bucket differs from the public one (section 3). The private store has never been exercised against a real provider. |
| 2 | **A new Neon project for production**, separate from `libraryhive-staging`. | The staging scheduler writes to the staging database every hour; production must never share it (section 2). |
| 3 | **Razorpay.** For the pilot leave `RAZORPAY_*` unset and have every pilot library enable UPI. | With no keys the checkout hides the gateway button (`library.gateway_enabled` is false) and a library without UPI shows "not taking online payments yet". Test keys (`rzp_test_…`) are refused when `ENVIRONMENT=production`; set live keys later to bring the gateway back. |
| 4 | **Email stays off** (`EMAIL_NOTIFICATIONS_ENABLED` unset). Owners learn about UPI requests from the badge on the Payments link and from in-app notifications. | No email provider is configured. |
| 5 | **Pin Python to 3.12 on Render.** Set the `PYTHON_VERSION` environment variable to a **fully qualified** 3.12 version (for example `3.12.x`, taking an available patch from Render's Python version page). | Render's default Python depends on when a service was created and is currently newer than the 3.12 that CI tests; Render's docs say a fully qualified version is required for `PYTHON_VERSION`. |

## 2. Neon (production database)

1. Create a **new Neon project** (for example `libraryhive-production`) in the region nearest the Render region. Do not reuse `libraryhive-staging` or its `production` branch: that branch holds staging data and the staging scheduler is bound to it.
2. Create a role that owns the schema. Copy the **direct** connection string (host without `-pooler`). Row locks (`select_for_update`) and the seat-concurrency rules need a session-level connection.
3. The string must end with `?sslmode=require`.
4. Neon's free plan scales to zero; the first request after idle is slow. `DB_CONN_MAX_AGE` (default 60 s) keeps connections open.
5. **Backup before the first migration and before every later one:** create a Neon branch from the production branch (a point-in-time copy), note its name, and keep it until the release is verified. Check your plan's restore window on Neon's pricing page; do not assume one.

## 3. Render (backend)

Create a **Web Service** with the **Python** runtime, connected to the GitHub repository.

| Setting | Value |
|---|---|
| Branch | `main` (after the UPI pull request is merged) |
| **Root Directory** | `backend` |
| **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| **Start Command** | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60` |
| **Health Check Path** | `/api/v1/health/` |
| Pre-Deploy Command | **leave empty**: migrations are a deliberate manual step (section 7) |
| Instance type | **verify** Render's current free and paid limits (idle spin-down, memory) before choosing; the pilot needs the service to be awake when students pay |

Why these values (checked against the code):

- `backend/manage.py`, `backend/requirements.txt` and the Django project package `config/` are all in `backend/`, so the root directory is `backend`.
- `config.wsgi:application` is the WSGI entry point and defaults to `config.settings.production`; `gunicorn` is pinned in `requirements.txt`.
- `collectstatic` is part of the build because production uses WhiteNoise's manifest storage (`STATIC_ROOT` is `backend/staticfiles`). **`manage.py` defaults to `config.settings.local`**, so `DJANGO_SETTINGS_MODULE=config.settings.production` must be set as an environment variable for the build to use production settings.
- The production settings are checked at import time, so **`SECRET_KEY`, `JWT_SIGNING_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` and the storage variables must exist before the first build**, even though `collectstatic` never connects to the database or the buckets.
- The health route is `GET /api/v1/health/` (200 with `db: ok`, or 503 if the database is unreachable). Render counts 2xx and 3xx as healthy and recommends 200 as the safest; without a path it only checks that the port is open. `config/settings/production.py` exempts exactly `^api/v1/health/$` from the HTTPS redirect, so a plain-HTTP probe gets 200 and not a 301. Checked locally with the production settings: probe 200, any other plain-HTTP path 301, an unknown host 400.
- If a deploy does not become healthy within Render's deploy window, Render keeps routing traffic to the previous deploy, so a bad first release does not replace a working one. Read the deploy log for the cause (host header, redirect, database, storage guard).

References: [Setting your Python version](https://render.com/docs/python-version), [How Render handles deploy failures](https://render.com/articles/how-render-handles-deploy-failures).

### Startup safety checks (what the app refuses)

With `ENVIRONMENT=production` the app **will not start** (`ImproperlyConfigured`, also failing `manage.py check --deploy`) if any of these is true. Messages name the variable, never its value:

- `DEBUG` is on, `SECRET_KEY` or `JWT_SIGNING_KEY` is short or equal to the other, `ALLOWED_HOSTS` or `CORS_ALLOWED_ORIGINS` is empty or `*`.
- A Razorpay test key (`rzp_test_…`) is set.
- `STORAGE_BACKEND` is not `s3`, or `AWS_STORAGE_BUCKET_NAME`, `AWS_PRIVATE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` is empty, or the private bucket equals the public bucket.

`ENVIRONMENT=staging` keeps accepting local storage and test keys. The GitHub `ci.yml` check supplies obviously fake placeholder storage values for this reason.

### Backend variables (names only)

| Variable | Value / note |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `PYTHON_VERSION` | fully qualified 3.12 version (blocker 5) |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `False` |
| `SECRET_KEY` | random, 50+ characters, **different** from `JWT_SIGNING_KEY` |
| `JWT_SIGNING_KEY` | random, 50+ characters |
| `DATABASE_URL` | Neon **direct** string, `sslmode=require` |
| `ALLOWED_HOSTS` | the service's `onrender.com` hostname exactly as the dashboard shows it, plus the custom API domain later; comma separated, no `*`. The default is `localhost`, which would make every request a 400. |
| `FRONTEND_URL` | the exact Vercel production origin, for example `https://app.example.com` (the cookie endpoints compare the `Origin` header with it) |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | the same origin, no `*` |
| `REFRESH_COOKIE_SECURE` | `True` (default) |
| `SECURE_SSL_REDIRECT` | default `True`; leave it |
| `SECURE_HSTS_SECONDS` | `0` at first (`check --deploy` shows the W004 notice, which is expected); raise to `31536000` only after HTTPS is verified on the final domain |
| `NUM_PROXIES` | `1` (one proxy hop) so throttling sees the real client address; **verify** with a test request |
| `ADMIN_URL` | a non-default path, for example `team-admin/` |
| `APP_VERSION` | the release tag or commit, shown by the health check |
| `STORAGE_BACKEND` | `s3` (required, see above) |
| `AWS_STORAGE_BUCKET_NAME` | the **public** photos bucket |
| `AWS_PRIVATE_BUCKET_NAME` | the **private** bucket (no public access, no listing) |
| `AWS_S3_ENDPOINT_URL` | the provider's S3 endpoint (blank for AWS itself) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | a key limited to those two buckets |
| `MEDIA_PUBLIC_BASE_URL` | the public bucket's HTTPS base (CDN or bucket domain) |
| `UPI_REVIEW_TARGET_HOURS` | optional, default `24`: after this a pending UPI request is flagged overdue to the student and the owner (nothing is decided automatically) |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | only with live keys (blocker 3) |
| `EMAIL_NOTIFICATIONS_ENABLED` | leave unset (off) |
| `LOG_LEVEL` | `INFO` |

Optional: `JOB_TRIGGER_TOKEN` (enables `/api/v1/internal/jobs/run/`; leave unset, the scheduler is GitHub Actions), `DB_CONN_MAX_AGE`, `SEAT_HOLD_MINUTES`.

Static files are served by WhiteNoise (collected at build). Media is not served by Django in production. The Django admin is reached at `ADMIN_URL`; create the first platform administrator after migrating (section 7). The UPI settings and requests are **not** registered in the Django admin: owners manage them in the app (see Rollback for the emergency route).

## 4. Vercel (frontend)

| Setting | Value |
|---|---|
| Framework | Next.js |
| **Root directory** | `frontend` |
| Install / build command | defaults (`npm ci`, `npm run build`); no output directory override |
| Node | the current LTS; the build was verified on Next 16.4.3 |

| Variable | Value / note |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<render-hostname>/api/v1` |
| `BACKEND_ORIGIN` | `https://<render-hostname>` (server side; `next.config.ts` rewrites `/api/v1/auth/*` through it so the refresh cookie is first-party) |
| `MEDIA_ORIGIN` | the public photo origin **and** the private bucket origin, comma separated (for example `https://photos.example.com,https://private-bucket.s3.example.com`). It feeds the CSP `img-src`; without the private origin the QR and screenshots will not display. |
| `NEXT_PUBLIC_MAP_TILE_URL`, `NEXT_PUBLIC_MAP_ATTRIBUTION` | optional, the map tile provider |

No Razorpay key is needed in the frontend. Domain and HTTPS: add the domain in Vercel, point DNS as Vercel instructs (only after approval); HTTPS is automatic. Then set `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` on Render to that exact origin and redeploy the backend.

## 5. GitHub (scheduled jobs)

The existing workflow `.github/workflows/scheduled-jobs.yml` is bound to the `staging` environment and `ENVIRONMENT: staging`. **Do not point it at production.** For production:

1. Create a GitHub Environment named `production` with deployment branches limited to `main`, no required reviewers and no wait timer (each scheduled run would otherwise wait).
2. Add **environment** secrets `DATABASE_URL` (the production Neon direct string), `SECRET_KEY`, `JWT_SIGNING_KEY` (new values, not the staging ones). Never as repository secrets.
3. Add a **separate** workflow file for production (a copy with `environment: production`, `ENVIRONMENT: production`, its own concurrency group names, and the storage variables the production guard now requires, since the job loads the production settings). Do not add it until the production database exists and has been migrated; do not run both workflows against the same database.
4. GitHub schedules are best-effort. Observed 2 to 7 November 2026 on `main`: the daily job ran on all 5 days but 7 to 8 hours late, and the hourly job fired about 15% of the time. Attendance auto-close still stamps the library's closing time, so history stays correct; a forgotten check-out blocks the student's next check-in until a run happens. A practical fallback is to add `auto_close_attendance` to the daily run (idempotent).

## 6. Private storage verification (do before the pilot)

Goal: prove, against the **real** provider, that the private bucket serves a QR or screenshot only through a short-lived signed link, and that nothing is publicly readable. Do this on a staging copy of the backend with `STORAGE_BACKEND=s3` and the real buckets and keys (never with production data). Treat any link you copy as sensitive for its 10 minutes of life.

1. **Upload through the app.** As an owner, upload a QR in **Payments, UPI settings**. Confirm the object appears in the **private** bucket under `payments/<library-id>/qr/<random>.webp`, and that nothing from this upload is in the public bucket (photos go to the public bucket only).
2. **Get the signed link.** The settings page and `GET /api/v1/owner/payment-settings/` return `qr_url`: a pre-signed URL that carries a signature and an expiry (`X-Amz-Expires=600` for signature version 4). Copy it from your browser's Network tab.
3. **It works while valid.** From a terminal: `curl -sI "<url>"` returns `200` and `content-type: image/webp`. Open it in a private browser window too. Then scan the QR image from the page with a phone.
4. **It is not guessable.** Change one character of the signature: expect `403` (`SignatureDoesNotMatch`). Remove the whole query string: expect `403` (`AccessDenied`).
5. **It expires.** Wait 11 minutes and request the same URL: expect `403` (`Request has expired`). Reload the page: a new link is issued and works.
6. **The bucket itself is private.** An anonymous request to the bucket root (`curl -s https://<endpoint>/<private-bucket>/`) must be `AccessDenied`, and so must a direct object URL without a signature. Also check the provider's console: no public access, no public-read policy or ACL on the private bucket.
7. **Students and other owners.** As a student with a live hold at that library, open the checkout: the QR must display. As a student without a hold, `GET /api/v1/student/libraries/<id>/upi-info/` must be 404. Submit a UTR with a screenshot; another owner and another student must get 404 for that request's screenshot endpoint.
8. **Browser policy.** In the browser's developer tools, confirm the image request goes to the origin listed in `MEDIA_ORIGIN` and the console shows no Content-Security-Policy violation. If the QR shows "could not be loaded", the usual cause is a private-bucket origin missing from `MEDIA_ORIGIN`.
9. **Local-file route is off.** `GET /api/v1/files/private/anything/` must answer 404 when `STORAGE_BACKEND=s3`.

If step 2 or 3 fails with a signature error, look at the provider's region and addressing style first: the settings pass the endpoint URL and keys but no region, so a bucket outside the provider's default region may need a region setting added. Record the exact error and fix it before the pilot.

## 7. First release and migrations (needs approval)

Order matters. Migrations in this release are **additive only** (`payments 0003`, `notifications 0003`), so the previous code keeps working against the new schema.

1. Create the Neon project and a backup branch (section 2).
2. Create the buckets and keys, and run section 6 on staging.
3. Create the Render service and set all variables (section 3). Leave the Pre-Deploy Command empty.
4. Deploy. The health check must go green. If it fails, read the deploy log (host header, redirect, database, storage guard).
5. Run migrations once, from your machine, against the production database (never from the deploy):
   ```bash
   cd backend
   # DATABASE_URL, SECRET_KEY, JWT_SIGNING_KEY, DJANGO_SETTINGS_MODULE, STORAGE_* etc. exported for production, in your shell only
   python manage.py migrate --check      # lists what is pending
   python manage.py migrate
   python manage.py createsuperuser      # the first platform administrator
   ```
6. Create the Vercel project and variables (section 4); deploy.
7. Smoke test (section 8). Only then add domains, raise HSTS and enable the production scheduler.

### Rollback

- **Code:** redeploy the previous deploy in Render (Events or Deploys, pick the earlier successful deploy, Rollback or redeploy) and promote the previous deployment in Vercel. The new tables are ignored by old code, so no schema change is needed. **Verify** the exact Render control names in the dashboard.
- **Data:** if a migration itself must be undone, restore from the Neon backup branch taken in step 1, or, for this release only, `python manage.py migrate payments 0002 && python manage.py migrate notifications 0002` (drops the two UPI tables and their rows; only before real UPI requests exist).
- **Switch UPI off for one library:** the owner turns off **Accept UPI payments** in **Payments, UPI settings**. The Django admin cannot do this (the model is not registered there). If the owner is unreachable, run this from your machine against the production database, with approval:
  ```bash
  python manage.py shell -c "from apps.payments.models import LibraryPaymentSettings as S; print(S.objects.filter(library__name='<library name>').update(upi_enabled=False))"
  ```

## 8. Production smoke test

1. `GET https://<api>/api/v1/health/` is 200 with `db: ok`; any other path over `http://` redirects, and `https://<api>/api/v1/schema/` is not public.
2. Register an owner and a student; log in; refresh the page (the session survives through the `lh_refresh` cookie); log out.
3. Owner: create a library, a plan, seats, upload a photo (appears via the public bucket), upload a QR, enter a UPI ID, switch UPI on.
4. The owner's **Payments** link shows a badge with the number of UPI payments waiting once a student sends a UTR (refreshes about every minute).
5. Student: open the library, hold a seat, see the QR, UPI ID and amount; send a UTR with a screenshot; the request shows **Waiting for the library**.
6. Owner: **Payments to check** shows it (and the notification opens that page); open the screenshot; approve with the confirmation box ticked. The member appears with an active membership and a receipt; the student's request shows **Approved** and they have exactly one notification.
7. Repeat with a second student: reject with a reason; the student sees the reason and the "does not refund" wording.
8. Try the same UTR again (409), approve the same request twice (second is 409), and view another library's request as a different owner (404).
9. Check **UPI settings** shows the live QR and that removing the UPI ID while UPI is on is refused.
10. A security-header spot check: `curl -sI` the frontend and the API for `Strict-Transport-Security` (after HSTS is raised), `X-Content-Type-Options` and the CSP.
11. Confirm no scheduler other than GitHub Actions is running against this database.
