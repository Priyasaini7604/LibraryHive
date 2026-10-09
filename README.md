# LibraryHive

"Strengthen Your Library & Attract More Students."

A multi-tenant platform connecting study libraries and students: library discovery, a live visual seat map, seat booking with online payment, memberships, offline student admission, attendance, complaints, visit requests and owner dashboards.

> **Status:** the approved design (Phases 0–7) is complete; the implementation is being built fresh from it (decision D19). The previous experimental code is preserved in the `legacy/*` git tags and is not part of the new implementation.

## Documentation

| Document | Purpose |
|---|---|
| [Library_Seat_Management_SRS_MVP.md](Library_Seat_Management_SRS_MVP.md) | Baseline requirements (SRS) |
| [FEATURES.md](FEATURES.md) | Final MVP scope, feature matrix, owners, decisions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture decision and system design |
| [SPEC.md](SPEC.md) / [ERDIAGRAM.md](ERDIAGRAM.md) | Data model and ER diagram |
| [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md) | Backend structure and API contracts |
| [UI_ARCHITECTURE.md](UI_ARCHITECTURE.md) | Frontend routes, screens, components |
| [SECURITY.md](SECURITY.md) | Security architecture and pre-launch requirements |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Tasks, owners, branches, order |
| [AGENTS.md](AGENTS.md) | Engineering rules for developers and AI agents |
| [PROJECT_AUDIT.md](PROJECT_AUDIT.md) | Audit of the code that existed before the approved design |

## Stack

Django + Django REST Framework · Next.js (App Router, TypeScript, Tailwind) · PostgreSQL · Razorpay.

## Local development

### 1. Database (PostgreSQL in Docker)

PostgreSQL runs only in Docker; nothing is installed on the host.

Requirements: Docker Desktop (Windows/macOS) or Docker Engine with the Compose plugin (Linux).

```bash
cp .env.example .env          # then edit .env and choose your own POSTGRES_PASSWORD
docker compose up -d db       # start PostgreSQL 16 on 127.0.0.1:5432
docker compose ps             # wait until the db service shows "healthy"
```

Useful commands:

```bash
docker compose stop db                      # stop (data is kept in the named volume)
docker compose logs -f db                   # view logs
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"   # SQL shell (values from .env)
docker compose down -v                      # DELETE the local database volume and start over
```

If port 5432 is already in use, set `POSTGRES_PORT` in `.env` (and use the same port in the backend's `DATABASE_URL`).

The Django test runner creates a separate `test_<name>` database in the same container automatically.

### 2. Backend (Django, Python 3.12+)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                  # then set SECRET_KEY, JWT_SIGNING_KEY and the DATABASE_URL password
python manage.py migrate              # creates tables, seeds vocabularies, creates the cache table
python manage.py runserver            # http://127.0.0.1:8000/api/v1/health/
```

Generate local keys with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Quality checks (the same ones CI runs):

```bash
ruff check . && ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py test                 # uses config.settings.test and a temporary test database
```

`manage.py` uses `config.settings.local` by default and `config.settings.test` for `manage.py test`; deployed processes use `config.settings.production`, which refuses to start with unsafe values.

### 3. Frontend (Next.js, Node.js 20.9+)

```bash
cd frontend
npm ci
cp .env.example .env.local            # NEXT_PUBLIC_API_URL, BACKEND_ORIGIN, MEDIA_ORIGIN
npm run dev                           # http://localhost:3000
```

Checks: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`. Details in [frontend/README.md](frontend/README.md).

Secrets (`.env`, `backend/.env`, `frontend/.env.local`) are git-ignored and must never be committed.

## Git workflow

- `main` is the stable integration branch; it only changes through reviewed pull requests.
- One short-lived branch per task: `feature/<task-name>` (see `IMPLEMENTATION_PLAN.md` §4), `fix/<issue>`, `docs/<doc>`, `chore/<topic>`.
- Commits follow Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Branches are deleted after merge. History on shared branches is never rewritten.
