# Browser end-to-end tests (Playwright)

These tests drive a real Chromium against a **separate stack and a separate database**. They never use a
development server, the normal `libraryhive` database, production data or real Razorpay credentials.

| Part | Where | Notes |
|---|---|---|
| Backend | `http://127.0.0.1:8010` | `config.settings.e2e` (see `backend/config/settings/e2e.py`) |
| Frontend | `http://127.0.0.1:3010` | production build in `.next-e2e` (so CSP and HSTS headers are the production ones) |
| Database | `libraryhive_e2e` on this machine | the only database the suite will open |
| Payments | local fake gateway + stubbed checkout window | no request is ever sent to Razorpay |

## Safeguards

1. `playwright.config.ts` refuses to start unless `E2E_DATABASE_URL` is a local URL whose database is named
   exactly `libraryhive_e2e` and differs from `DATABASE_URL`.
2. `config/settings/e2e.py` repeats the check (`config/e2e_guard.py`, unit tested in
   `apps/core/tests/test_e2e_guard.py`) and then **overwrites** `DATABASE_URL` with the e2e URL before any
   setting is read, so `backend/.env` cannot redirect the process to another database.
3. The Razorpay keys are dummy values set by the e2e settings; any real key in your environment is ignored.
   The browser never reaches `checkout.razorpay.com`: the tests replace the checkout script with a stub
   that signs with the dummy secret, so the server's real HMAC verification still runs.
4. `manage.py e2e_prepare` only migrates and seeds. It never creates, drops, truncates or resets a database.
5. Throttle rates are raised in the e2e settings only (the suite logs in many times from one address).

## One-time setup (a person runs this)

Create the database once. This is the only command that creates anything outside the repository:

```bash
# from the repository root, with the Docker database running
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE libraryhive_e2e;"'
```

Install the browser once: `npm run e2e:install`.

## Run

Set `E2E_DATABASE_URL` to the same server with the database name `libraryhive_e2e`, and `E2E_PYTHON` to the
backend virtualenv's Python if `python` is not it.

```bash
# PowerShell
$env:E2E_DATABASE_URL = "postgres://<user>:<password>@localhost:5432/libraryhive_e2e"
$env:E2E_PYTHON = "..\backend\.venv\Scripts\python.exe"

# prepare the database (migrate + demo data); safe to repeat
cd backend
$env:DJANGO_SETTINGS_MODULE = "config.settings.e2e"
..\backend\.venv\Scripts\python.exe manage.py e2e_prepare

# run the suite (starts and stops both servers itself)
cd ..\frontend
npm run e2e
```

Tests create their own uniquely named accounts, so they can be re-run without resetting the database.
To start from scratch a person drops and recreates `libraryhive_e2e` by hand; nothing here does it.

## What is covered, and what is not

Covered: security headers and CSP in a real browser, registration, login, logout, token storage and cookie flags,
role checks, tenant isolation, discovery, the library page, seat holds and fake-payment checkout (success,
failure, dismissed), owner admission with cash, and the student account claim.

Not provable here: HSTS from the Django side (needs HTTPS and a real host), a real Razorpay checkout and
webhook delivery (see the manual checklist), email delivery, and production hosting behaviour.
