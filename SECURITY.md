# LibraryHive — Security Architecture (Phase 6)

**Version:** 1.0
**Date:** 2026-10-09
**Status:** Draft, awaiting approval
**Builds on:** `ARCHITECTURE.md` §11–§13, §19 · `SPEC.md` v2.0 · `BACKEND_ARCHITECTURE.md` (endpoint numbers like #42 refer to it) · `UI_ARCHITECTURE.md` · `PROJECT_AUDIT.md` §19 (security findings S1–S12)

**Labels:** `[CONTROL]` required implementation · `[TEST]` required automated test · `[DECISION REQUIRED]` needs a decision by the team · `[PRE-LAUNCH REQUIREMENT]` must be done before real users or real money

**Not legal advice.** This document does not contain or finalise legal text. Terms of Service, Privacy Policy, contact information and any data-protection compliance review are listed as pre-launch requirements in §19 and must be prepared by the team (with qualified advice where needed).

---

## 1. Security goals and the three non-negotiable guarantees

| # | Guarantee | Where it is enforced | Proof |
|---|---|---|---|
| **G1** | **Owner A must never access Library B's private data.** | Server: role permission + library-scoped querysets + service ownership checks on every referenced ID (§6) | `test_isolation.py` in every app (§6.4), CI-blocking |
| **G2** | **Student A must never read or modify Student B's private data.** | Server: student-scoped querysets + service ownership checks (§6) | Same isolation suites |
| **G3** | **Payment success is never trusted from the browser.** | Server: amount from the DB, HMAC-verified checkout signature or signed webhook, idempotent confirmation under a row lock (§10) | Payment security tests (§10.5) |

Other goals, in order: integrity of seats, memberships and money (no double booking, no lost history); confidentiality of personal data; availability of discovery and booking; accountability (audit trail).

---

## 2. Threat model (summary)

### 2.1 Assets

| Asset | Why it matters |
|---|---|
| Student personal data (name, phone, email, exam domain, attendance) | Privacy; misuse for spam or stalking |
| Owner business data (members, revenue, dues) | Commercially sensitive; competitor access |
| Payment records and gateway secrets | Financial loss, fraud |
| Seat availability and memberships | Core service integrity (double booking, fake occupancy) |
| Accounts and tokens | Takeover leads to all of the above |
| Audit trail | Accountability, dispute resolution |

### 2.2 Actors

| Actor | Capability assumed |
|---|---|
| Anonymous internet user / bot | Can call any public endpoint at high volume; can register accounts |
| Malicious student | Valid student account; can tamper with requests, replay calls, guess IDs |
| Malicious owner | Valid owner account for their own library; wants other libraries' data or to abuse student identities |
| Someone who knows a student's phone/email | Tries to take over an offline record or reset a password |
| Network attacker | Can observe or tamper with traffic not protected by TLS |
| Forged gateway sender | Sends fake payment callbacks or webhooks |
| Compromised dependency / leaked secret | Code or key exposure (the current committed `SECRET_KEY` is already in git history) |

### 2.3 Top threats and primary mitigations

| Threat | Mitigation (section) |
|---|---|
| Cross-tenant data access by changing IDs (IDOR) | Scoped querysets, 404 for out-of-scope, ownership checks on body IDs (§6) |
| Privilege escalation (student → owner actions) | Role permissions on every view, default deny (§5) |
| Fake payment success / amount tampering | Server-side amount, HMAC verification, signed webhooks, idempotency (§10) |
| Double booking via races | Row locks + partial unique constraints (SPEC §4.1; not repeated here) |
| Account takeover (credential stuffing, OTP guessing, offline-record hijack) | Throttling, hashed one-time codes with attempt limits, verified claim, refresh-token rotation (§3, §4) |
| XSS stealing tokens | No raw HTML, strict CSP, refresh token not readable by JavaScript (§4.3) |
| Malicious file upload | Content verification, re-encode, size and pixel limits, random names (§9) |
| Secret leakage | Env-only secrets, rotation, startup guard, redaction in logs (§13, §16) |
| Abuse / scraping / spam | Rate limits, pagination caps, neutral responses (§12) |
| Data loss / tampering of history | No hard deletes, PROTECT FKs, append-only audit log, backups (§14) |

---

## 3. Authentication and password security

| Control | Requirement |
|---|---|
| Password hashing `[CONTROL]` | Django's default PBKDF2-SHA256 (current Django iteration count). Never stored or logged in plain text. Argon2 is an acceptable later upgrade; Django re-hashes on login automatically. |
| Password policy `[CONTROL]` | Django validators on register, claim and reset: minimum length **8**, not similar to name/email, not a common password, not entirely numeric. The serializer's current `min_length=6` (PROJECT_AUDIT S5) is removed. |
| Login `[CONTROL]` | Email + password. **Generic** `INVALID_CREDENTIALS` for every failure (wrong password, unknown email, unclaimed offline record, deactivated user). Throttled per IP and per email (BACKEND §4.5). Failures logged as security events with a masked email. |
| Lockout | No permanent lockout (to avoid denial of service against a victim); throttling slows guessing. |
| Account enumeration `[CONTROL]` | Login, forgot password (#13a) and claim start (#12) give neutral responses. **Registration** reveals `EMAIL_TAKEN` / `PHONE_TAKEN`; this is a documented, accepted trade-off for usability and is throttled. |
| One-time codes `[CONTROL]` | Claim OTP, owner claim code and password-reset code (`AccountClaim`): generated with `secrets`; 6 digits (owner code: 8 characters from an unambiguous alphabet); **stored hashed**; compared in constant time; single use; expiry (10 min / 30 min / 7 days); maximum 5 attempts, then revoked; issuing a new code revokes the old one; never logged, never returned by any API except the one-time display to the owner who issued it. |
| Offline-record claim (G2) `[CONTROL]` | Never auto-linked by phone or email. Requires the email OTP (to the email on the record) or the owner-issued code (handed over in person). Names are never used for matching (SPEC §4.6). |
| Password reset `[CONTROL]` | Successful reset **blacklists every outstanding refresh token** of the user and sends a "password changed" email. |
| Deactivated users `[CONTROL]` | Rejected at login and on every token use (`is_active` check). |
| Owner self-registration | Open (D11). Abuse is limited by throttling and by the publish rules (an owner's library only appears publicly once it is complete). Fraudulent libraries are handled manually by the team through Django admin. `[DECISION REQUIRED]` for any future owner verification (FEATURES AUTH-13, P2). |
| Multi-factor authentication | Not in the MVP. Recommended later for owners and for Django admin staff. |

---

## 4. JWT and session strategy

### 4.1 Token parameters `[CONTROL]`

| Setting | Value |
|---|---|
| Access token lifetime | 60 minutes (AGENTS §4.1) |
| Refresh token lifetime | 7 days |
| Rotation | `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True` (reuse of an old refresh token fails) |
| Logout | Blacklists the refresh token (#9) |
| Claims | `user_id`, `role`, `name` only (no email, phone or permissions list) |
| Signing | HS256 with `SIGNING_KEY` = a dedicated secret (not `SECRET_KEY`), rotated if leaked (rotation signs everyone out) |
| Role trust | The role claim is used only for UI routing. The server always re-reads `request.user.role` from the database. |

### 4.2 Where tokens are kept (re-evaluation promised in ARCHITECTURE §11)

| Option | XSS impact | Complexity |
|---|---|---|
| A. Access + refresh in `localStorage` (current plan) | An XSS bug can steal **both** tokens; the attacker keeps access for up to 7 days | Lowest |
| **B. Access token in memory; refresh token in an `HttpOnly; Secure; SameSite=Strict` cookie** | An XSS bug can act only while the page is open and cannot read the refresh token; stolen access tokens expire within 60 min | Moderate: needs the auth endpoints on the same site as the frontend |
| C. Full cookie-session auth for all API calls | Strong | Requires CSRF protection on every mutating endpoint and a same-site proxy for all traffic |

**Recommendation: Option B (decision SEC-1).** It removes the most damaging consequence of XSS (long-lived token theft) for a small, contained change. Option A was explicitly flagged for re-evaluation in ARCHITECTURE §11, and the brief ranks security above MVP speed.

How it works:
- The frontend proxies **only** `/api/v1/auth/*` through a Next.js rewrite, so the refresh cookie is first-party to the frontend's domain (scoped to path `/api/v1/auth/`). All other API calls continue to go directly to the backend with `Authorization: Bearer <access>`.
- On page load, `AuthProvider` calls `POST /auth/refresh/`. The cookie is sent automatically and a new access token comes back in the body and is kept in memory only.
- Login, claim completion and refresh **set** the cookie; logout and password reset **clear** it and blacklist the token.

**SEC-1 was approved on 2026-10-09.** The following amendments have been applied:
- `ARCHITECTURE.md` §11 and `AGENTS.md` §4.1 (token storage).
- `BACKEND_ARCHITECTURE.md` #6, #7, #8, #9, #13: the refresh token moves from the JSON body and response to the cookie.
- `UI_ARCHITECTURE.md` §9.2 and §9.4: in-memory access token; refresh on load.

### 4.3 CSRF for the cookie endpoints `[CONTROL]`

Only the refresh, login, logout and claim-complete endpoints read or set the cookie. They require **all** of the following:
1. `SameSite=Strict` on the cookie.
2. A JSON body (`Content-Type: application/json`).
3. An `Origin` header matching `FRONTEND_URL`, otherwise 403.

Bearer-token endpoints are not exposed to CSRF (browsers do not attach the header automatically). Django's CSRF middleware stays enabled for Django admin (session-based).

(Option A is no longer in use; SEC-1 is approved.)

---

## 5. Role-based access control

`[CONTROL]` Default deny: `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`. Public endpoints opt in with `AllowAny`, and the list of public endpoints is fixed:

> `/health/`, `/meta/*`, `GET /libraries/`, `GET /libraries/{id}/`, `GET /libraries/{id}/seats/`, `/auth/register|login|refresh|claim/*|password-reset/*`, `/payments/webhook/razorpay/` (signature-protected), `/internal/jobs/run/` (token-protected, disabled unless configured), `/schema/` (non-production only).

| Namespace | Permission | Notes |
|---|---|---|
| `/student/*` | `IsAuthenticated` + `IsStudent` | Owners get 403 |
| `/owner/*` | `IsAuthenticated` + `IsOwner` (+ `HasLibrary`) | Students get 403 |
| `/payments/orders/`, `/payments/verify/` | `IsStudent` | Owners cannot create orders |
| `/notifications/*`, `/auth/me`, `/auth/logout` | `IsAuthenticated` | Own records only |
| Django admin | `is_staff` | Team members only (§15) |

`[TEST]` A route-inventory test lists every URL pattern and fails if a view is `AllowAny` but not on the list above. This prevents a forgotten permission from silently making an endpoint public (PROJECT_AUDIT S3).

---

## 6. Object-level authorization and multi-tenant isolation

### 6.1 Rules `[CONTROL]`

1. **Owner scope = `request.user.library`.** Owner URLs never contain a library ID (BACKEND §3), so there is no library ID to tamper with.
2. **All owner and student list and detail views use the scoped mixins** (`OwnerLibraryScopedMixin`, `StudentOwnedScopedMixin`). An object outside scope is simply not found: **404**, so the existence of other tenants' IDs is never confirmed.
3. **Every ID inside a request body is re-checked by the service** against the caller's scope before use. Examples: `seat_id` and `plan_id` in an admission (#54) must be in the owner's library; `hold_id` or `membership_id` in an order (#41) must belong to the student; `library_id` in a complaint (#71) must be a library where the student has or had a membership; `membership_id` in manual check-in (#68) must be in the owner's library.
4. **Denormalised `library_id`** (SeatHold, Payment, AttendanceRecord, Complaint, Notification) is **always copied from the parent row by the service, never taken from input**.
5. **Analytics, reports and CSV exports** call selectors that take the library as a required argument; there is no "all libraries" code path outside Django admin.
6. **Public endpoints never return personal data.** The seat map returns status only, never holder or occupant identity. Library pages show the library's public contact details only, and domain counts are aggregates.
7. **Cross-tenant identity:** a student is a global identity, but an owner sees a student's contact details only through a relationship with **their** library (membership, payment, attendance, complaint, visit, admission). The admission lookup (#53) returns a **masked** phone and email for an existing student until the owner commits the admission.

### 6.2 Explicit verification: G1 (Owner A vs Library B)

| Attack | Result |
|---|---|
| Owner A calls `/owner/members/{B_membership_id}/` | 404 (scoped queryset) |
| Owner A archives B's membership, records a renewal on it, releases B's hold | 404 |
| Owner A admits a student to `seat_id` from Library B | 404 from the service ownership check |
| Owner A reads `/owner/payments/`, `/owner/dues/`, reports, exports or audit log | Only Library A rows, by construction |
| Owner A issues a claim code for a student who is only a member of Library B | 404 |
| Owner A reads B's complaints, visits or attendance | 404 / not listed |
| Owner A edits B's library, plans, photos or seats | Impossible: there is no library ID in owner URLs; plan, photo and seat IDs from B give 404 |

### 6.3 Explicit verification: G2 (Student A vs Student B)

| Attack | Result |
|---|---|
| Student A reads `/student/memberships/{B_id}/`, `/student/payments/{B_id}/`, `/student/complaints/{B_id}/` | 404 |
| Student A creates an order (#41) for B's hold or membership | 404 |
| Student A verifies a payment (#42) with B's order ID | 404 (lookup is scoped to the caller) |
| Student A cancels B's hold (#40) or visit (#79) | 404 |
| Student A checks in using B's membership | Impossible: check-in uses only the caller's own membership at the given library |
| Student A marks B's notification as read | 404 |
| Student A claims B's offline record | Needs B's email OTP or B's owner-issued code (§3) |
| Student A resets B's password | Needs the code sent to B's email (§3) |
| Student A sees who holds or occupies a seat | Not exposed by the public seat map |

### 6.4 Isolation tests `[TEST]`

Each app's `tests/test_isolation.py` builds Library A and Library B, Owner A and Owner B, and Students A and B with memberships in each library. It then asserts every row in §6.2 and §6.3, plus "no B rows in any A list, report or export". These suites are **CI-blocking** (Phase 11).

---

## 7. Input validation

| Control | Requirement |
|---|---|
| Layers `[CONTROL]` | Serializer (types, formats, lengths, enums, ranges) → service (cross-row rules, ownership, state) → database constraints (BACKEND §7). The frontend's zod validation is for convenience only. |
| Strict schemas `[CONTROL]` | Input serializers declare fields explicitly; unknown fields are ignored and never mass-assigned. Read-only fields (`id`, `library`, `student`, `status`, `amount`, `receipt_number`…) can never be set by clients. |
| Money and amounts `[CONTROL]` | Clients never send an amount. Payment amounts come from `PricingPlan.price`. |
| Text `[CONTROL]` | Trimmed; maximum lengths enforced in serializer and DB; stored as plain text; **no HTML accepted or rendered** (the frontend escapes everything and never uses `dangerouslySetInnerHTML`). |
| Identifiers | UUIDs validated by the URL converters; malformed IDs return 404. |
| Phones and emails | Normalised by one helper (`phonenumbers`, Indian numbers only in the MVP); emails lowercased and validated. |
| Dates | Ranges checked in services against the business date (Asia/Kolkata), e.g. visit date within today to today + 60. |
| Query parameters | Whitelisted filters and sort keys; `page_size` capped at 100; radius capped at 50 km. Raw SQL is never built from input; only the ORM is used. |
| Request size `[CONTROL]` | `DATA_UPLOAD_MAX_MEMORY_SIZE` 1 MB for JSON; uploads capped by `FILE_UPLOAD_MAX_MEMORY_SIZE` and the 5 MB rule; the web server or platform request limit is set accordingly. |
| Open redirects `[CONTROL]` | The frontend accepts `?next=` only as a relative same-origin path starting with `/` and not `//`. |
| CSV export injection `[CONTROL]` | Cells beginning with `= + - @` (and tab or carriage return) are prefixed with `'` (BACKEND #87). |

---

## 8. Frontend and browser security

| Control | Requirement |
|---|---|
| Content-Security-Policy `[CONTROL]` | Set by Next.js headers: `default-src 'self'`; `script-src 'self' https://checkout.razorpay.com` (plus the nonce/hash approach Next.js needs for its own inline scripts); `connect-src 'self' {API_ORIGIN} https://api.razorpay.com https://nominatim.openstreetmap.org`; `img-src 'self' data: {MEDIA_ORIGIN} https://*.tile.openstreetmap.org`; `frame-src https://api.razorpay.com https://checkout.razorpay.com`; `style-src 'self' 'unsafe-inline'` (Tailwind/Leaflet runtime styles); `object-src 'none'`; `base-uri 'self'`; `frame-ancestors 'none'`. The exact Razorpay domains are confirmed against Razorpay's current documentation during implementation. |
| Other headers `[CONTROL]` | `Strict-Transport-Security` (production), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: geolocation=(self), camera=(), microphone=()` |
| No secrets in the bundle `[CONTROL]` | Only `NEXT_PUBLIC_API_URL` is public. The Razorpay key ID arrives with each order (it is public by design). |
| Safe rendering | React escaping only. External links use `rel="noopener noreferrer"`. User-supplied URLs are never rendered as links. |
| Third parties | Only Razorpay Checkout, OpenStreetMap tiles and Nominatim (UI §9.5). No analytics or tracking scripts in the MVP. Adding any later requires a CSP and privacy review. |
| Geocoding privacy (U2 revisited) | The area text a user types is sent from the browser to Nominatim (with the user's IP). Accepted for the MVP because it is an area name, sent only on explicit search, and never combined with account data. **It must be disclosed in the Privacy Policy** `[PRE-LAUNCH REQUIREMENT]`. Moving the call behind the backend is an option if this is unacceptable. |

---

## 9. File upload security

`[CONTROL]` Pipeline (BACKEND §12):
1. Authenticated owner only (photos); student only for their own complaint image (P1).
2. Request-size cap; reject over **5 MB** before processing.
3. Ignore the client filename and `Content-Type`.
4. `Pillow` `verify()` then reopen; format must be JPEG, PNG or WEBP.
5. Reject images over **40 megapixels** (decompression bombs; also `Image.MAX_IMAGE_PIXELS`).
6. **Re-encode** to WEBP at a maximum of 1920 px, which strips EXIF and GPS metadata and any embedded payload. The original is not stored.
7. Store under a random UUID key in a tenant prefix (`libraries/{library_id}/…`); path traversal is impossible because no user text is used in the key.
8. Serve photos from object storage or CDN on a **separate origin** from the app, with `Content-Type: image/webp` and `X-Content-Type-Options: nosniff`.
9. Complaint images live in a **private** bucket or prefix and are served only through 10-minute signed URLs to the complaining student and that library's owner.
10. Limits: 15 photos per library; upload throttle 30 per hour per user.
11. Storage credentials are write-limited to the app's bucket (least privilege, §13).

`[TEST]` Oversize file, a non-image renamed `.jpg`, an SVG, a decompression bomb, EXIF removed after upload, another owner's photo ID gives 404.

---

## 10. Payment security (G3)

### 10.1 Principles `[CONTROL]`

1. **The browser is never trusted.** The checkout success callback is only a hint that triggers server verification.
2. **The amount is decided by the server** from `PricingPlan.price` when the order is created, and stored on the `Payment` row. The verify step ignores any amount the client might send.
3. **Card and UPI data never touch LibraryHive servers.** Payment details are entered only in Razorpay's hosted Checkout, which keeps the system out of direct card-data handling. Formal compliance obligations (e.g. PCI DSS self-assessment scope) are to be confirmed with Razorpay during merchant onboarding `[PRE-LAUNCH REQUIREMENT]`.
4. **Secrets:** `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` exist only in backend environment variables; separate test and live keys; live keys only in production.

### 10.2 Checkout verification (#42)

- The `Payment` is looked up by `razorpay_order_id` **within the caller's own payments** (G2).
- `expected = HMAC_SHA256(key_secret, order_id + "|" + payment_id)`; compared with `hmac.compare_digest`.
- On mismatch: 400 `INVALID_SIGNATURE`, a `security.invalid_payment_signature` log event, and **no state change**.
- On match: `confirm_payment()` locks the Payment row; already `success` → returns the stored result (idempotent).

### 10.3 Webhook verification (#43)

- The **raw request body** is read before parsing; the signature from `X-Razorpay-Signature` is verified with the webhook secret using a constant-time compare.
- Invalid signature: 400, logged, **not stored** (forged traffic cannot fill the database).
- Valid: the event is inserted with a unique `event_id`, and a replay is a no-op. Processing calls the same idempotent `confirm_payment()`.
- The endpoint is CSRF-exempt and unauthenticated by design (the signature is its authentication), and is throttled.
- Optional hardening: allow-list Razorpay's published webhook IP ranges at the platform level if the host supports it (not relied on).

### 10.4 Integrity rules

- Unique `gateway_order_id`, `gateway_payment_id` and webhook `event_id` (SPEC §3.11–3.12).
- Payment state transitions are restricted (SPEC §4.3). Amount, plan, period and student are immutable after creation; there is no delete.
- Offline payments are recorded only by the owner of the membership's library, with `recorded_by`, a sequential receipt number and an audit row.
- Reconciliation queries Razorpay for stale pending orders using server credentials only (BACKEND §10).
- `needs_refund` cases are surfaced to the owner and student; refunds are manual (PAY-14) and the outcome is recorded by the team. The refund/cancellation policy text is `[PRE-LAUNCH REQUIREMENT]` (§19).

### 10.5 Payment security tests `[TEST]`

Forged checkout signature; signature computed with the wrong secret; valid signature but another student's order ID (404); client-supplied amount ignored; webhook with an invalid signature (400, nothing stored); webhook replayed 3 times (one confirmation); verify and webhook racing (one confirmation); late capture after hold expiry (confirms or `needs_refund`, never two members on one seat).

---

## 11. CORS, CSRF and transport

| Control | Requirement |
|---|---|
| HTTPS `[CONTROL]` | HTTPS only in production. `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER` (behind the platform proxy), HSTS (1 year after verification, include subdomains once the domain is stable). |
| CORS `[CONTROL]` | `CORS_ALLOWED_ORIGINS` from the environment: exactly the production frontend origin (and preview origins only in staging). Never `*`. `CORS_ALLOW_CREDENTIALS` stays **false** (cookies only travel on the same-site auth proxy, §4.2). Allowed headers: `Authorization`, `Content-Type`, `X-Request-ID`. |
| CSRF `[CONTROL]` | §4.3 for the cookie endpoints; Django CSRF for admin; Bearer endpoints are not CSRF-exposed. `CSRF_TRUSTED_ORIGINS` set to the admin origin. |
| Hosts `[CONTROL]` | `ALLOWED_HOSTS` from the environment (no `*`, fixing S2). |
| Clickjacking | `X-Frame-Options: DENY` (backend) and `frame-ancestors 'none'` (frontend). |

---

## 12. Rate limiting and abuse prevention

`[CONTROL]` DRF scoped throttles with the database cache (no Redis), rates in BACKEND §4.5: login, register, claim start/complete, password reset, hold creation, uploads, webhook, plus anonymous and user defaults.

- Throttling uses the client IP from the platform's trusted forwarding header **only when** configured with the correct number of proxies (otherwise `X-Forwarded-For` is spoofable). This is set per host in Phase 10 `[CONTROL]`.
- A hold limit per student per library already prevents seat hoarding (SPEC §3.9). The 15-minute expiry limits seat-blocking abuse; repeated hold-and-abandon by one account is visible in logs and can be blocked by deactivating the account.
- Pagination caps and the 50 km radius cap limit scraping cost.
- 429 responses use the envelope and are logged as `security.rate_limited`.

---

## 13. Secrets management and environment variables

| Control | Requirement |
|---|---|
| Source `[CONTROL]` | All secrets come from environment variables, set in the hosting platforms' secret stores and GitHub Actions secrets. Never in code, git, Docker images, logs, error messages or the frontend bundle. |
| `.env` files | `backend/.env` and `frontend/.env.local` are git-ignored (already). The `.env.example` files contain **placeholders only**. |
| Startup guard `[CONTROL]` | `production.py` refuses to start if `DEBUG` is true, `SECRET_KEY` or `SIGNING_KEY` is missing/short/default, `ALLOWED_HOSTS` or `CORS_ALLOWED_ORIGINS` contains `*`, or Razorpay **test** keys are configured with `ENVIRONMENT=production`. |
| Leaked key (S1) `[CONTROL]` `[PRE-LAUNCH REQUIREMENT]` | The `SECRET_KEY` committed in `backend/config/settings.py` is permanently in git history and **must never be used in any deployed environment**. New keys are generated per environment. Rewriting git history is not required, because the key will never be used. |
| Separation | Separate secrets per environment (local, staging, production); Razorpay test keys outside production. |
| Rotation | Documented in `DEPLOYMENT.md` (Phase 10): `SECRET_KEY`/`SIGNING_KEY` (rotating `SIGNING_KEY` signs everyone out), Razorpay keys and webhook secret, storage keys, DB password, email credentials, `JOB_TRIGGER_TOKEN`. Rotate immediately on suspected exposure or when a team member with access leaves. |
| Access | Only the team members who deploy have access to production secrets. |
| Secret scanning | GitHub secret scanning / push protection enabled on the repository (Phase 11). |

---

## 14. Database security

| Control | Requirement |
|---|---|
| Network | Managed PostgreSQL with TLS (`sslmode=require`); not publicly reachable where the host allows private networking, otherwise restricted credentials plus TLS. |
| Least privilege `[CONTROL]` | The application connects as a dedicated role that owns the app schema; it is not a cluster superuser. A separate read-only role may be created for ad-hoc analysis. |
| Injection | ORM only; no string-built SQL. Any raw SQL (e.g. the receipt sequence) uses parameters. |
| Integrity | Constraints from SPEC (partial uniques, checks, PROTECT FKs). History tables are never hard-deleted; the audit log is append-only at application level. |
| Backups | Automated daily backups with point-in-time recovery if the provider offers it; a restore test before launch `[PRE-LAUNCH REQUIREMENT]` (Phase 10). |
| Data in tests | Tests and seed data use fake data only. Production data is never copied to local machines. |
| Encryption at rest | Provided by the managed database and object storage. Application-level encryption of fields is not needed for the MVP's data (no government ID numbers or card data are stored). |

---

## 15. API and platform security

| Control | Requirement |
|---|---|
| Error handling `[CONTROL]` | One exception handler. Clients never see stack traces, SQL, settings or file paths; unexpected errors return a generic 500 with `request_id`. `DEBUG=False` in every deployed environment. |
| Schema exposure | `/schema/` is public only in local/staging; staff-only in production. |
| Django admin `[CONTROL]` | Mounted at a non-default path from `ADMIN_URL`; staff accounts only for team members; strong unique passwords; `AuditLog` is read-only in admin; admin actions that change memberships or payments are discouraged in favour of the product flows. MFA for admin is recommended post-MVP. |
| Method restrictions | Views declare allowed methods explicitly; no unused PUT/DELETE handlers (removes the current PUT-as-PATCH alias). |
| Internal job trigger | Disabled unless `JOB_TRIGGER_TOKEN` is set; token compared in constant time; 404 otherwise. |
| Dependencies `[CONTROL]` | Pinned versions; `pip-audit` and `npm audit --omit=dev` in CI; Dependabot (or equivalent) for security updates; the global-freeze `requirements.txt` (with unrelated packages) is removed, reducing attack surface. |
| Health endpoint | Returns status only; no version numbers of dependencies or environment details. |

---

## 16. Logging and monitoring

| Control | Requirement |
|---|---|
| Security events `[CONTROL]` | Logged per BACKEND §14.1: login success and failure, logout, refresh failures, 403s, rate limits, invalid payment or webhook signatures, claim and password-reset attempts and failures, admin logins. |
| Redaction `[CONTROL]` `[TEST]` | Passwords, tokens, cookies, `Authorization` headers, OTP and claim codes, signatures and secrets are dropped. Emails and phones are masked. Request bodies are not logged. |
| Correlation | Every log line has `request_id`; it is returned in `X-Request-ID` and shown in UI error messages for support. |
| Access to logs | Only team members with platform access. Logs can contain masked personal data, so they are treated as confidential. |
| Retention | Platform retention for application logs (LOG-10); audit rows kept in the database. |
| Alerting (minimum) | Platform alerts on deploy failure, health-check failure and the scheduled job exiting non-zero. A spike of `security.*` events is reviewed manually in the MVP. Hosted error tracking is P2 (LOG-11). |

---

## 17. Sensitive data protection

### 17.1 Personal data inventory

| Data | Where stored | Who can see it | Protection |
|---|---|---|---|
| Name | `User` | Self; owners of libraries the student has a relationship with; team (admin) | — |
| Email | `User` | Self; related owners; team | Masked in logs and admission lookup; neutral auth responses |
| Phone | `User` | Self; related owners; team | Masked in logs and admission lookup |
| Exam domain | `User` | Self; related owners; **aggregated** publicly (counts only) | Only counts are public |
| Password | `User` (hash) | Nobody | PBKDF2 hash |
| One-time codes | `AccountClaim` (hash) | Nobody (owner sees an owner code once when issuing it) | Hashed, expiring, attempt-limited |
| Attendance times | `AttendanceRecord` | Self; that library's owner; team | Library-scoped |
| Payments (amounts, method, receipt) | `Payment` | Self; that library's owner; team | Library-scoped; no card or UPI credentials stored |
| Gateway identifiers | `Payment`, `PaymentWebhookEvent` | Team; owner sees receipt-level info | Webhook payloads may contain payer contact details; access limited to admin |
| Complaint text and image (P1) | `Complaint` + private storage | Self; that library's owner; team | Private bucket, signed URLs |
| IP address | `AuditLog` | Owner sees their audit log **without IP**; team sees IP | Used only for security investigation |
| Location | Not stored | — | Browser geolocation is used only to query nearby libraries and is not sent to logs or saved |

**Data minimisation `[CONTROL]`:** the MVP does **not** collect government ID numbers (e.g. Aadhaar), photo IDs, date of birth, addresses of students, or card or bank details. FEATURES v1.0 mentioned "Photo ID details" for offline admission; this is **not collected** in the approved scope. Adding any such field requires a security and privacy review.

### 17.2 Data-subject and legal topics

| Topic | Status |
|---|---|
| Privacy Policy describing what is collected, why, who sees it (including owners), third parties (Razorpay, OpenStreetMap/Nominatim, email provider, hosting), retention and contact | `[PRE-LAUNCH REQUIREMENT]` `[DECISION REQUIRED]`: text to be written by the team; not drafted here |
| Applicable Indian data-protection obligations (for example the Digital Personal Data Protection Act, 2023 and its rules), including consent wording at registration and offline admission, grievance contact and data-retention or erasure requests | `[DECISION REQUIRED]` `[PRE-LAUNCH REQUIREMENT]`: requires a review by someone qualified; this document does not assess compliance |
| Consent for offline admission (an owner enters a student's data before the student has an account) | `[DECISION REQUIRED]`: how the student is informed, and the owner's responsibility, must be covered in the Terms and Privacy Policy |
| Account deletion or data-export requests | Not an MVP feature. Requests are handled manually by the team (deactivation; history retained where needed for financial records). The policy must describe this `[PRE-LAUNCH REQUIREMENT]`. |

---

## 18. Current-code findings → controls (PROJECT_AUDIT §19)

| Finding | Control | Phase |
|---|---|---|
| S1 Hardcoded `SECRET_KEY` in git | §13: env-only, startup guard, never reuse the leaked key | 8 |
| S2 `DEBUG=True`, `ALLOWED_HOSTS=*` | §11, §13 startup guard | 8 |
| S3 Default permission AllowAny | §5 default deny + route-inventory test | 8 |
| S4 No rate limiting | §12 | 8 |
| S5 Weak password policy | §3 Django validators | 8 |
| S6 Open owner self-registration | §3: accepted (D11), throttled; publish rules | 8 |
| S7 Demo credentials prefilled in UI | Removed with `owner/setup` (UI §15) | 8 |
| S8 JWT in `localStorage` | §4.2 SEC-1 (in-memory access + HttpOnly refresh cookie) | 8 |
| S9 Unvalidated seat status from clients | Seat status no longer writable (derived, SPEC §4.1) | 8 |
| S10 Unsafe auto-link of offline records | §3 verified claim (SPEC §4.6) | 8 |
| S11 Phone not unique or normalised | SPEC §3.1 unique E.164 | 8 |
| S12 CORS hardcoded | §11 env-driven allow-list | 8 |

---

## 19. Pre-launch requirements and decisions

### 19.1 Legal and contact content (U8; not drafted here)

| ID | Item | Status |
|---|---|---|
| L1 | **Terms of Service** (student and owner use, booking and hold rules, owner responsibilities for member data, acceptable use) | `[DECISION REQUIRED]` `[PRE-LAUNCH REQUIREMENT]` |
| L2 | **Privacy Policy** (inventory in §17.1, third parties, retention, rights and requests, offline-admission data) | `[DECISION REQUIRED]` `[PRE-LAUNCH REQUIREMENT]` |
| L3 | **Contact information**, including support email, a grievance or data-protection contact, and the business identity shown on the site | `[DECISION REQUIRED]` `[PRE-LAUNCH REQUIREMENT]` |
| L4 | **Refund and cancellation policy** (covers `needs_refund` cases and manual refunds). Payment gateways commonly ask for refund, terms, privacy and contact pages during merchant activation; confirm Razorpay's exact requirements during KYC. | `[DECISION REQUIRED]` `[PRE-LAUNCH REQUIREMENT]` |
| L5 | Data-protection compliance review (§17.2) | `[DECISION REQUIRED]` `[PRE-LAUNCH REQUIREMENT]` |

The UI has placeholder links for L1–L4 (UI §4.1). **The product must not launch with empty or placeholder legal pages.** This is checked in the final audit (Phase 12).

### 19.2 Other pre-launch security items

| Item | Phase |
|---|---|
| Generate fresh secrets per environment; confirm the leaked key is unused | 10 |
| Razorpay live activation with webhook secret configured; live keys only in production | 10 |
| Backup restore test | 10 |
| Trusted-proxy configuration for client IPs (throttling) | 10 |
| HSTS enabled after HTTPS is verified on the final domain | 10 |
| GitHub secret scanning and dependency alerts enabled | 11 |
| Manual security pass: isolation matrix, payment tests, upload tests, CSP check in the browser console | 9 |

### 19.3 Security decisions

| ID | Decision | Recommendation |
|---|---|---|
| **SEC-1** | Token storage: Option B (in-memory access token + HttpOnly refresh cookie via a same-site auth proxy) instead of `localStorage` | **APPROVED 2026-10-09.** Changes the approved ARCHITECTURE §11 and endpoints #6–#9 and #13; all amendments listed in §4.2 have been applied (ARCHITECTURE, AGENTS, BACKEND_ARCHITECTURE, UI_ARCHITECTURE). |
| SEC-2 | MFA for owners and admin | Post-MVP (P2) |
| SEC-3 | Owner verification before publishing | Post-MVP (AUTH-13, P2); manual moderation via admin until then |
| SEC-4 | Geocoding from the browser (U2) | Keep for the MVP with Privacy Policy disclosure (§8) |

---

## 20. Security test checklist (feeds Phase 9)

| Area | Tests |
|---|---|
| Auth | Generic login errors; throttling; password validators; refresh rotation and reuse rejected; logout blacklists; reset signs out all sessions; deactivated user rejected |
| One-time codes | Hashed at rest; expiry; single use; 5-attempt lock; new code revokes old; neutral responses for unknown identities |
| RBAC | Route-inventory test (no unexpected `AllowAny`); student→owner endpoints 403; owner→student endpoints 403 |
| Isolation (G1, G2) | §6.2 and §6.3 matrices in every app |
| Payments (G3) | §10.5 |
| Uploads | §9 tests |
| Validation | Unknown fields ignored; read-only fields not writable; caps on page size and radius; CSV injection escaped; `next` redirect validation (frontend) |
| Headers | CSP and security headers present on frontend responses; HSTS, nosniff, frame options on backend responses in production settings |
| Logging | Redaction filter; no tokens or codes in captured logs; `request_id` present |
| Secrets | Production settings refuse to start with `DEBUG=True` or a default or short key |
