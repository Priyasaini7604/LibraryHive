# LibraryHive — Agent & Developer Engineering Guidelines

**Document Version:** 1.3 (aligned with all approved phase documents and decision D19, 2026-10-09)  
**Applies To:** All Software Engineers, Technical Contributors, and AI Coding Agents  
**Target Repositories:** `LibraryHive` (Backend: Django/DRF, Frontend: Next.js/TypeScript)  
**Status:** Mandatory Engineering Contract  

---

## 1. Prime Directives for AI Agents & Developers

Before writing, modifying, or reviewing any code in this repository, every AI agent and human developer **MUST** adhere to the following non-negotiable rules:

1. **Read Specifications First:** Always read `AGENTS.md`, `FEATURES.md`, `ARCHITECTURE.md` and `SPEC.md` before writing code or planning architecture. `SPEC.md` is the source of truth for the data model.
2. **Strict MVP Scope Compliance:** Implement ONLY what is defined in the MVP scope. **NEVER** move an MVP requirement to "future", and **NEVER** invent unrequested features.
3. **Zero Fake / Mocked Functionality:** Never use fake `setTimeout` mocks, hardcoded mock arrays, fake payment success simulations, or simulated database queries for real product features. Every feature must hit real API endpoints, real database tables, and real services.
4. **Backend Truth & Validation:** Business logic, authorization, pricing calculations, expiry dates, and concurrency rules **MUST** be enforced on the Django backend. Never trust client-side validation alone.
5. **Never Bypass Authentication / Authorization:** Every endpoint must be protected by appropriate permissions (`IsAuthenticated`, `IsOwner`, `IsStudent`, `IsLibraryOwnerOf`). Never expose unprotected mutative APIs.
6. **Never Trust Frontend Payment Success:** Payment records must never be finalized based on a frontend callback. Razorpay payments must be cryptographically verified server-side via HMAC SHA-256 signatures or signed webhooks.
7. **Absolute Concurrency Control:** Seat booking and reservations must prevent race conditions and double-booking at the database level using atomic transactions, row-level locks (`select_for_update`) and the partial unique constraints defined in `SPEC.md`.
8. **Idempotent Notifications:** Automated membership expiry notifications must be deduplicated by the unique `Notification.dedup_key` (`SPEC.md` §4.5), so re-running a job never sends a repeated alert.
9. **No Over-Engineering:** Do not introduce unrequested microservices, Redis queues, Celery, Kafka, Docker Swarm, Kubernetes, or AI/LLM models unless explicitly instructed in writing. Keep the architecture a clean, reliable modular monolith.

---

## 2. Architecture & Codebase Structure Rules

### 2.1 Monolith Structure
```
LibraryHive/
├── backend/                       # Django 6.0+ & DRF Modular Backend
│   ├── config/                    # Django configuration (settings, urls, wsgi, asgi)
│   ├── apps/
│   │   ├── core/                  # Base models, permissions, tenant mixins, exception handler, logging, audit log, vocabularies
│   │   ├── accounts/              # User model, JWT authentication, profiles, offline-account claim
│   │   ├── libraries/             # Library profiles, photos, amenities, pricing plans
│   │   ├── seats/                 # Seat inventory, layout generator, reservation locks
│   │   ├── memberships/           # Membership lifecycle, offline student admission
│   │   ├── payments/              # Gateway adapter (gateway.py), orders, verification, webhooks, offline payments, dues
│   │   ├── notifications/         # In-app notifications, email deliveries, scheduled job
│   │   ├── attendance/            # Student self-check-in, owner live roster
│   │   ├── complaints/            # Grievance ticketing & resolution workflow
│   │   ├── visits/                # Demo & visit requests scheduling
│   │   └── analytics/             # Owner/student KPI aggregations, domain charts, CSV export
│   ├── media/                     # Local dev uploads only (production uses S3-compatible object storage)
│   ├── manage.py
│   └── requirements.txt
│
└── frontend/                      # Next.js 16 App Router, React 19, TypeScript (strict), Tailwind CSS
    ├── app/
    │   ├── (public)/              # Landing, discover, public library pages
    │   ├── (auth)/                # Login, registration, account claim
    │   ├── student/               # Student portal (discover, library view, dashboard)
    │   └── owner/                 # Owner admin panel (setup, seats, members, dues, complaints)
    ├── components/
    │   ├── ui/                    # Reusable atom components (button, modal, badge, alert)
    │   ├── seat-map/              # Interactive visual seat grid & selection component
    │   └── charts/                # Occupancy & domain distribution charts
    ├── lib/
    │   ├── api-client.ts          # Centralized fetch wrapper with JWT interceptor
    │   ├── auth.ts                # Token storage & session helper
    │   └── types.ts               # Shared TypeScript interfaces mirroring API contracts
    ├── package.json
    └── tsconfig.json
```

### 2.2 Backend Architectural Standards
- **App Modularity:** Each app in `backend/apps/` must own its models, serializers, views, urls, and unit tests.
- **Service Layer:** State changes happen only in `services.py`; read queries live in `selectors.py`; views stay thin (parse, permission, service, envelope). Cross-app calls go through the other app's services/selectors (`ARCHITECTURE.md` §8.2).
- **Database:** PostgreSQL in every environment, including local development and CI. SQLite is not supported (row locks are no-ops on SQLite).
- **Defaults:** `DEFAULT_PERMISSION_CLASSES = IsAuthenticated`; public endpoints opt in explicitly with `AllowAny`.
- **Base Models:** All domain entities must inherit from `apps.core.models.BaseModel`, providing an immutable UUID primary key (`id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`), `created_at`, and `updated_at`.
- **URL Versioning:** All API routes must be registered under `/api/v1/` only (no duplicate `/api/` mount) and cleanly linked in `backend/config/urls.py`.
- **Response Format:** All endpoints must return the standardized response envelope. Failures additionally carry `error_code`, `details` and `request_id` (full definition in `BACKEND_ARCHITECTURE.md` §4.1 and §6):
  ```python
  return Response({
      "success": True,
      "data": serializer.data,
      "error": None
  }, status=status.HTTP_200_OK)
  ```
- **Error Format:** Any failure or validation exception must return:
  ```python
  return Response({
      "success": False,
      "data": None,
      "error": "Descriptive error message"
  }, status=status.HTTP_400_BAD_REQUEST)
  ```

### 2.3 Frontend Architectural Standards
- **Next.js App Router:** Use Next.js 16 App Router conventions (`layout.tsx`, `page.tsx`, `loading.tsx`, `error.tsx`).
- **Styling & UI kit:** Tailwind CSS plus shared components in `components/ui/`. No new inline-style pages; existing ones are migrated when touched.
- **Data & forms:** TanStack Query for server data; react-hook-form + zod for forms.
- **Client vs. Server Components:** By default, pages requiring user interactivity, state, or client-side auth must declare `"use client";` at the very top.
- **Centralized API Calls:** All network requests must flow through `frontend/lib/api-client.ts`. Never write raw `fetch("http://...")` calls inside individual UI components.
- **Strict Typing:** Never use `any` when defining API payloads, component props, or state. Use the explicit interfaces in `frontend/lib/types.ts`.
- **Comprehensive UI States:** Every screen and component must explicitly handle:
  1. *Loading State:* Visual skeleton or spinner.
  2. *Error State:* User-friendly error message with retry button.
  3. *Empty State:* Clean illustration/message when no records exist.
  4. *Success / Loaded State:* Full data rendering.

---

## 3. Database & Concurrency Rules

### 3.1 Concurrency & Race Condition Prevention
- Seat status is **derived, never stored** (`SPEC.md` §4.1): disabled, then occupied (active membership), then reserved (live hold), else empty.
- Any action that mutates seat availability (`create_hold`, `confirm_payment`, `admit_offline_student`, `archive_membership`) **MUST** be wrapped in `transaction.atomic()` and follow the locking protocol in `SPEC.md` §4.1.
- Use row-level locking:
  ```python
  seat = Seat.objects.select_for_update().get(id=seat_id)
  ```
- Check for overlapping active memberships and unexpired reservations within the same lock before granting a reservation.
- Seat holds expire after `SEAT_HOLD_MINUTES` (15). A hold is live only if `status='pending' AND expires_at > now()`; expired holds are treated as dead on every read, even before cleanup.
- Map violations of partial unique constraints to HTTP 409.

### 3.2 Offline & Online Student Deduplication
- Identity keys are normalised phone (E.164) and lowercased email, both unique. **Never match by name.**
- When an owner adds an offline student, look up by phone and email separately and follow the decision table in `SPEC.md` §4.6 (a conflicting match is rejected with 409).
- If new, create a user with `is_offline=True` and an unusable password (`user.set_unusable_password()`).
- When a student signs up online and matches an offline record, **do not auto-link**. Require a verified claim (email OTP or owner-issued claim code, `AccountClaim`). Only after verification convert the same `User` row to an online account.

### 3.3 Relational Pricing (full-day seats, decision D1)
- Always reference `PricingPlan` via foreign key in `Membership` and `Payment`. Never hardcode fee amounts or durations in controllers; payment amounts are copied from the plan on the server.
- Seats are sold full-day (one active membership per seat). `PricingPlan.timing_note` is descriptive only. Per-shift selling is out of MVP scope.
- Plans referenced by memberships or payments are deactivated, never deleted.

---

## 4. Authentication, Authorization & Multi-Tenancy

### 4.1 JWT Handling
- Access tokens expire in 60 minutes; Refresh tokens expire in 7 days.
- Custom JWT claims must embed: `user_id`, `role`, `name`.
- Token storage (SEC-1, `SECURITY.md` §4.2): the **access token is kept in memory only** (never in `localStorage`/`sessionStorage`) and sent as `Authorization: Bearer <token>`. The **refresh token is an `HttpOnly; Secure; SameSite=Strict` cookie** scoped to `/api/v1/auth/`, reached through the frontend's same-site rewrite for `/api/v1/auth/*`. The cookie endpoints require a JSON body and a matching `Origin` header.

### 4.2 Multi-Tenant Data Isolation
- An owner belongs to exactly one `Library`.
- All owner queries must be scoped to the owner's library:
  ```python
  def get_queryset(self):
      return Membership.objects.filter(library=self.request.user.library)
  ```
- Objects outside the caller's tenant scope are fetched through scoped querysets and therefore return **HTTP 404** (does not reveal that the ID exists). Wrong role returns **403**. (Changed from 403 by `ARCHITECTURE.md` §10.)

---

## 5. Payment Gateway (Razorpay) Integration Rules

1. **Step 1 — Create Order (Server-Side):**
   - The backend validates the plan price and calls `razorpay_client.order.create({ "amount": int(price * 100), "currency": "INR", "receipt": ... })`.
   - Returns `order_id`, `key_id`, and `amount` to the frontend.
2. **Step 2 — Checkout (Client-Side):**
   - The frontend opens the Razorpay modal.
   - Upon payment, Razorpay returns `razorpay_payment_id`, `razorpay_order_id`, `razorpay_signature`.
3. **Step 3 — Cryptographic Signature Verification (Server-Side):**
   - The frontend sends the 3 parameters to `/api/v1/payments/verify/`.
   - The backend computes the HMAC SHA-256 signature using `settings.RAZORPAY_KEY_SECRET`.
   - Only upon cryptographic match does the backend:
     - Mark `Payment.status = 'success'` (idempotent: lock the payment row, no-op if already success)
     - Complete the `SeatHold` and create the active `Membership` (the seat then derives as occupied)
   - The signed webhook runs the same idempotent confirmation; callback and webhook may arrive in any order.
4. **Step 4 — Offline Cash Payment:**
   - Owners can record offline payments (endpoint defined in `BACKEND_ARCHITECTURE.md`).
   - Generates a verified internal receipt number and tracks `recorded_by=request.user`.

---

## 6. Notification Deduplication Rules

1. Scheduled work runs through one idempotent management command, run hourly by the host's cron:
   ```bash
   python manage.py run_scheduled_jobs
   ```
2. It identifies memberships due in 3 days, due today, or newly overdue (statuses are derived from `next_due_date`).
3. Every notification has a deterministic `dedup_key` (`SPEC.md` §4.5) and is inserted with `ON CONFLICT DO NOTHING`:
   ```python
   Notification.objects.bulk_create(notifications, ignore_conflicts=True)
   ```
4. Email deliveries are tracked in `NotificationDelivery` (pending, then sent or failed, max 5 attempts) and retried by the same job.

---

## 7. File Upload & Storage Rules

- Media files must be uploaded via `multipart/form-data`.
- Maximum upload size: **5 MB**.
- Allowed extensions: `.jpg`, `.jpeg`, `.png`, `.webp`.
- Always generate random UUID filenames to prevent collision and directory traversal:
  ```python
  def library_photo_path(instance, filename):
      ext = filename.split('.')[-1].lower()
      return f"libraries/{instance.library.id}/{uuid.uuid4()}.{ext}"
  ```
- In development, serve uploaded media from `/media/` using `django.conf.urls.static.static`.

---

## 8. Error Handling & Logging Standards

- Never let an unhandled 500 error leak to the frontend.
- DRF views must catch known exceptions (`ValidationError`, `PermissionDenied`, `ConflictError`, `NotFound`) and return structured JSON.
- Critical operations (payment verification, booking conflicts, offline deduplication) must write structured log messages:
  ```python
  logger.info("Payment verified successfully", extra={"order_id": order_id, "student_id": str(user.id)})
  logger.warning("Seat booking conflict detected", extra={"seat_id": str(seat.id), "student_id": str(user.id)})
  ```

---

## 9. Automated Testing Standards

Every developer and agent must write automated unit and integration tests for every new feature:
1. **Accounts:** Test user registration, duplicate email/phone rejection, login, and token refresh.
2. **Libraries:** Test library creation, photo upload, plan editing, and multi-tenant permission blocking.
3. **Seats & Concurrency:** Test parallel booking attempts to ensure no double-booking occurs.
4. **Memberships & Offline Admission:** Test offline walk-in student admission, seat assignment, and online account linking.
5. **Payments:** Test signature verification success and forged signature rejection.
6. **Notifications:** Test that repeated execution of the expiry command does not create duplicate notification rows.

To run tests:
```bash
python manage.py test apps.accounts apps.libraries apps.seats apps.memberships apps.payments
```

---

## 10. Git, Branching & Commit Conventions

- `main` is the only long-lived branch and the stable integration branch. All work happens on short-lived branches merged through reviewed PRs.
- Shared-repository operations (push, PR creation by automation, merge into `main`, deleting remote branches or tags, history rewrites, force-push) require explicit confirmation from the project lead. History of shared branches is never rewritten.
- Local PostgreSQL runs in Docker (`docker-compose.yml`); see `README.md`.

- **Branch Naming:**
  - `feature/<task-name>` as listed in `IMPLEMENTATION_PLAN.md` §4 (e.g. `feature/platform-foundation`, `feature/seat-holds`)
  - `chore/<topic>` for repository maintenance (e.g. `chore/legacy-cleanup`)
  - `fix/<issue-name>` (e.g. `fix/seat-concurrency-lock`)
  - `docs/<doc-name>` (e.g. `docs/api-spec-update`)
- **Commit Messages:** Follow Conventional Commits:
  - `feat: implement offline student registration endpoint`
  - `fix: prevent double booking via select_for_update in seat reservation`
  - `test: add unit tests for razorpay signature verification`
  - `docs: update API endpoints in SPEC.md`
- **Clean Diffs:** Never commit `.env`, `node_modules`, `__pycache__`, `db.sqlite3`, or build artifacts.

---

## 11. Environment Variables Specification

### 11.1 Backend (`backend/.env`)
```bash
# Django Core
SECRET_KEY=your-super-secret-key-at-least-50-characters
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL in every environment)
DATABASE_URL=postgres://postgres:your_password@localhost:5432/libraryhive_db

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Razorpay Payment Gateway (Test or Live)
RAZORPAY_KEY_ID=rzp_test_YourKeyIdHere
RAZORPAY_KEY_SECRET=YourRazorpaySecretKeyHere
RAZORPAY_WEBHOOK_SECRET=YourWebhookSecretHere

# Media storage: local in development, S3-compatible in production
STORAGE_BACKEND=local
MEDIA_URL=/media/
MEDIA_ROOT=media/

# Email (console backend in development; a transactional provider in production)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=LibraryHive <no-reply@example.com>

# Full variable list: BACKEND_ARCHITECTURE.md section 13
```

### 11.2 Frontend (`frontend/.env.local`)
```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
# No Razorpay key here: the public key id is returned by the order API (payments/orders/)
```

---

## 12. Final Definition of Done (DoD) Checklist

Before submitting code, verify:
- [ ] Requirements match `SPEC.md` and `FEATURES.md` exactly.
- [ ] No fake or mock data is left in frontend or backend.
- [ ] Concurrency locks are applied on seat reservations.
- [ ] Offline student registration links cleanly with online registration.
- [ ] Razorpay payment verification uses cryptographic server-side checks.
- [ ] Expiry notifications do not generate duplicates on repeated cron runs.
- [ ] Multi-tenant object-level permissions block cross-library access.
- [ ] Backend tests pass cleanly with `python manage.py test`.
- [ ] Frontend builds without TypeScript or Next.js compilation errors (`npm run build`).
- [ ] UI is fully responsive and includes proper loading, error, and empty states.
