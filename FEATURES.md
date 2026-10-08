# LibraryHive — Final MVP Feature Scope

**Version:** 2.2 (Phase 1: Final MVP Scope). Supersedes v1.0 of this file. v2.2 adds AUTH-15 (forgot password), approved by the user during Phase 5.
**Date:** 2026-10-09
**Status:** Decisions D1–D17 approved (recommended defaults accepted on 2026-10-09). Awaiting final Phase 1 sign-off.
**Inputs merged:**
1. Baseline SRS: `Library_Seat_Management_SRS_MVP.md` (cited as `SRS §x` / `FR-xx`)
2. Approved new MVP requirements from the product brief, sections A to L (cited as `NEW-A` … `NEW-L`)
3. Approved addition after Phase 0: application logs (cited as `NEW-LOG`)
4. Useful details from `FEATURES.md` v1.0 (cited as `F1`)
5. Implementation status verified in `PROJECT_AUDIT.md` (cited as `AUDIT §x`)

> **Rule:** BASE SRS + APPROVED NEW REQUIREMENTS = FINAL MVP SCOPE. No SRS requirement has been removed. No approved new requirement has been downgraded. Where sources conflict, the newer approved requirement wins and the conflict is recorded in §6.

---

## 1. Legend

**Priority**
- **P0**: must work for the MVP launch.
- **P1**: important but secondary. Built after all P0 items in the same module.
- **P2**: future. Not built in the MVP.

**Status** (verified against code in `PROJECT_AUDIT.md`)
- **IMPLEMENTED**: UI + API + DB + validation + authorization + tests all exist.
- **PARTIALLY IMPLEMENTED**: some layers exist.
- **NOT IMPLEMENTED**: nothing usable exists.
- **BLOCKED**: cannot start until a dependency or external item exists.
- **REQUIRES DECISION**: the scope of the item depends on an open decision (none remain as of v2.1; see §5).

**Owner** is the **final** owner from Phase 7 (`IMPLEMENTATION_PLAN.md` §2, assigned by backend app). Each feature has exactly one owner. Changes from the earlier tentative owners are explained in `IMPLEMENTATION_PLAN.md` §2.2.

| Person | Area (final, by app) |
|---|---|
| **P1** | Platform & identity: `core`, `accounts`, settings, logging/audit, CI, deployment, frontend foundation, auth and profile screens |
| **P2** | Library & seats: `libraries`, `seats` (configuration and holds), `visits`; discovery, library page, seat map, owner onboarding, library settings, seat manager |
| **P3** | Membership & payments: `memberships`, `payments`; checkout, renewal, admission, members, dues, payments screens |
| **P4** | Operations & insights: `notifications`, `attendance`, `complaints`, `analytics`; dashboards, notifications, attendance, complaints, reports, activity log |

**Definition of "complete"** (applies to every row): UI + API + database + validation + authorization + error handling + automated tests all work. A UI alone does not make a feature complete.

---

## 2. MVP scope at a glance

| # | Module | P0 features (incl. "P0 if approved") | Current state |
|---|---|---|---|
| 1 | Platform, auth and RBAC | 13 | Partial (backend auth only) |
| 2 | Library profile and owner onboarding | 7 | Partial |
| 3 | Library photos | 5 | Not implemented |
| 4 | Discovery and explore | 6 | Partial |
| 5 | Seat management and visual seat map | 8 | Partial |
| 6 | Booking and reservation | 6 | Not implemented |
| 7 | Membership lifecycle | 8 | Not implemented |
| 8 | Offline students and identity linking | 5 | Not implemented |
| 9 | Payments (online and offline) | 11 | Not implemented |
| 10 | Notifications (renewal and expiry) | 7 | Not implemented |
| 11 | Attendance | 5 | Not implemented |
| 12 | Complaints | 5 | Not implemented |
| 13 | Demo / visit requests | 4 | Not implemented |
| 14 | Dashboards, analytics and reports | 8 | Partial (domain chart only) |
| 15 | Logging and audit trail (**new**) | 8 | Not implemented |
| 16 | Cross-cutting quality, deployment and CI/CD | 7 | Not implemented |

---

## 3. Feature matrix

### 3.1 Platform, authentication and RBAC

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| AUTH-01 | Owner registration | SRS §7.1, NEW-A | P0 | PARTIALLY IMPLEMENTED (API only; no page, no envelope, no tests; AUDIT §5) | P1 | An owner registers with name, email, phone and password. Duplicate email or phone is rejected with a clear error. Django password validators are applied. A registration page exists. |
| AUTH-02 | Student registration | SRS §3.1, NEW-B | P0 | PARTIALLY IMPLEMENTED (API only) | P1 | A student registers with name, email, phone, password and domain. Duplicate checks behave as in AUTH-01. If an offline record matches, the claim flow (OFF-04) is triggered instead of an error. |
| AUTH-03 | Login and logout | SRS §2.4, NEW-A/B | P0 | PARTIALLY IMPLEMENTED (JWT login API; login UI exists only inside the owner wizard; logout clears client only) | P1 | Login with email and password returns access and refresh tokens carrying `user_id`, `role` and `name`. Invalid credentials give a generic error. Logout invalidates the refresh token server-side. A dedicated login page redirects by role. |
| AUTH-04 | Session handling and token refresh | AGENTS §4.1 | P0 | PARTIALLY IMPLEMENTED (refresh endpoint exists; lifetimes not configured; frontend never refreshes) | P1 | Access token lasts 60 min and refresh token 7 days, set in config. The frontend refreshes transparently once on a 401, then redirects to login. |
| AUTH-05 | Owner profile view and edit | NEW-A | P0 | PARTIALLY IMPLEMENTED (GET `/auth/me/` only) | P1 | The owner can view and edit name and phone. Email changes are not allowed in the MVP. |
| AUTH-06 | Student profile view and edit, including domain/exam | SRS §5.1, NEW-B | P0 | PARTIALLY IMPLEMENTED (GET only) | P1 | The student can view and edit name, phone and domain. Domain is chosen from a controlled list (see LIB-04). |
| AUTH-07 | Role-based access control (owner / student / public) | SRS §4.5, NFR-01 | P0 | PARTIALLY IMPLEMENTED (`IsOwner`, `IsStudent` exist; default permission is AllowAny; AUDIT §6) | P1 | Every endpoint declares its permission, and the default is deny (authenticated). A student gets 403 on every owner endpoint and vice versa. Covered by tests. |
| AUTH-08 | Multi-tenant isolation | SRS §2.5, NFR-01 | P0 | PARTIALLY IMPLEMENTED (library and seat mutations only, tested) | P1 | Owner A gets 403 or 404 on **every** read or write of Library B's private data (members, payments, attendance, complaints, visits, notifications, audit log, reports). Student A cannot read or modify Student B's bookings, memberships, payments, complaints or attendance. Each module has its own tests. |
| AUTH-09 | Public browsing without login | SRS §3.1, NEW-B | P0 | IMPLEMENTED (discovery, explore, seat map) | P2 | Discovery, the library profile, photos, plans and the seat map load anonymously. Booking, payment, complaints, demo requests and attendance require login and redirect to it. |
| AUTH-10 | Frontend route protection and role-aware navigation | AGENTS §2.3 | P0 | NOT IMPLEMENTED | P1 | `/owner/*` routes require the owner role and `/student/*` account pages require the student role. The header shows role menus and logout. |
| AUTH-11 | Rate limiting on auth endpoints | Phase 0 S4 | P0 | NOT IMPLEMENTED | P1 | Login, register and claim endpoints are throttled. Exceeding the limit returns 429 in the standard envelope. |
| AUTH-12 | Standard response envelope and error handling on all APIs | AGENTS §2.2, §8 | P0 | PARTIALLY IMPLEMENTED (library and seat views only) | P1 | Every response, including auth and validation errors, uses `{success, data, error}`. No raw 500 page reaches the client. |
| AUTH-13 | Owner verification or invite before going live | Phase 0 D11 | P2 | NOT IMPLEMENTED | — | D11: MVP uses open owner self-registration. Spam libraries are kept out of discovery by the LIB-07 publish rules. |
| AUTH-14 | Login by phone number | F1 §5.2.1 | P2 | NOT IMPLEMENTED | — | D13: email login only in the MVP. |
| AUTH-15 | Forgot / reset password (owner and student) | Added by user approval (Phase 4 follow-up) | P0 | NOT IMPLEMENTED | P1 | The user enters their email on a Forgot password page and always sees the same neutral confirmation, whether or not an account exists. If an active online account matches, a 6-digit code is emailed (valid 30 min, single use, 5 attempts). Entering the code and a new password (Django validators apply) changes the password and signs the user out of every device (all refresh tokens are blacklisted). Throttled. Audited. Unclaimed offline records get no email and are pointed to the claim flow. **This needs a working transactional email provider from the first release** (also required for the claim OTP in OFF-04); only notification emails (NOT-08) stay P1. |

### 3.2 Library profile and owner onboarding

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| LIB-01 | One-time onboarding wizard (create library) | FR-01, SRS §7.1 | P0 | PARTIALLY IMPLEMENTED (`owner/setup`; demo credentials prefilled; AUDIT §16) | P2 | A newly registered owner is guided to create exactly one library (a second attempt returns 409). There are no hardcoded credentials. The wizard can be resumed. |
| LIB-02 | Edit library profile: name, description, address, coordinates, contact phone and email, opening and closing hours | FR-01, NEW-A | P0 | PARTIALLY IMPLEMENTED (no description field) | P2 | All fields can be edited by the owning owner only. Coordinates are validated (lat −90..90, lng −180..180). Unset coordinates are stored as NULL, not 0. |
| LIB-03 | Facilities / amenities stored per library | NEW-A, F1 §5.1.2 | P0 | NOT IMPLEMENTED (frontend hardcodes amenities, which is fake data) | P2 | The owner selects amenities from a controlled list. Discovery and explore pages show **only** the library's real amenities. |
| LIB-04 | Domains catered (controlled list) | FR-01, FR-12 | P0 | PARTIALLY IMPLEMENTED (free comma string) | P2 | Domains come from one shared vocabulary used by libraries, students and analytics. |
| LIB-05 | Pricing plans: add, edit and deactivate | FR-01, NEW-A | P0 | PARTIALLY IMPLEMENTED (plans are deleted and recreated on every save, which breaks history; AUDIT §16.9) | P2 | Plans have name, duration in days and price (> 0). Editing never deletes a plan that memberships reference; such plans are deactivated instead. Inactive plans are hidden from booking. |
| LIB-06 | Library seat capacity derived from configured seats | FR-01 | P0 | PARTIALLY IMPLEMENTED (denormalised `total_seats` can drift) | P2 | Displayed capacity always equals the number of active seats. |
| LIB-07 | Library visibility: draft vs published | F1 Workflow 1, D12 | P0 | NOT IMPLEMENTED | P2 | A library is auto-published, and appears in discovery, only once it has a name, address, coordinates, at least 1 active plan and at least 1 seat. Until then it is a draft visible only to its owner. |

### 3.3 Library photos (new)

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| PHO-01 | Upload multiple photos | NEW-A | P0 | NOT IMPLEMENTED | P2 | The owner uploads JPG, PNG or WEBP files of 5 MB or less each, up to 15 photos per library (approved default). Files go to file/object storage with random UUID names. The DB stores only references. Invalid type or size is rejected server-side. |
| PHO-02 | Preview and gallery management | NEW-A | P0 | NOT IMPLEMENTED | P2 | The owner sees thumbnails of all photos and the upload progress or result. |
| PHO-03 | Delete photo | NEW-A | P0 | NOT IMPLEMENTED | P2 | The owner deletes their own photo. The stored file is removed. Deleting the cover photo clears or reassigns the cover. |
| PHO-04 | Select primary/cover photo | NEW-A | P0 | NOT IMPLEMENTED | P2 | Exactly one cover per library at most, enforced by the DB. The cover appears on discovery cards and the explore header. |
| PHO-05 | Student-facing photo gallery | NEW-A/B | P0 | NOT IMPLEMENTED | P2 | The explore page shows a gallery with a viewer that works on mobile and an empty state when there are no photos. |
| PHO-06 | Captions and reordering | F1 §5.1.3 | P1 | NOT IMPLEMENTED | P2 | The owner can set a caption and display order. |

### 3.4 Discovery and explore

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| DIS-01 | Nearby discovery by current location or searched area | FR-03 | P0 | IMPLEMENTED (haversine radius filter, tested) | P2 | Results sorted by distance show distance in km, available seats and starting price. |
| DIS-02 | Keyword search and filters (domain, amenity) | FR-03, NEW-B | P0 | PARTIALLY IMPLEMENTED (keyword and domain filters; amenity filter missing) | P2 | Filters combine. An empty result shows an empty state. |
| DIS-03 | Discovery result cards with cover photo and real data | NEW-A/B | P0 | PARTIALLY IMPLEMENTED (no cover; hardcoded facility badges) | P2 | Cards show cover (or a placeholder), real amenities, available seats, starting price and distance. |
| DIS-04 | Map view (map/list toggle) | SRS §1.3, FR-03 | P0 | NOT IMPLEMENTED | P2 | Libraries are shown as markers. Clicking a marker opens the library card. The map provider is chosen in Phase 2 and must be free-tier compatible. |
| DIS-05 | Public library explore page: profile, location, timings, facilities, plans, photos, domain breakdown, seat map | FR-04, NEW-B | P0 | PARTIALLY IMPLEMENTED (facilities fake, no photos, domain counts always 0) | P2 | All sections use real API data, with loading, error and empty states. |
| DIS-06 | Pagination and performance of library list | NFR-04 | P0 | NOT IMPLEMENTED (N+1 queries, no pagination) | P2 | The list is paginated and the query count does not grow per library. |

### 3.5 Seat management and visual seat map

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| SEAT-01 | Grid generator (rows × seats per row) | FR-02, F1 | P0 | IMPLEMENTED (API + tests + wizard) | P2 | Generates uniquely labelled seats. Re-running it never resets existing seats' state. |
| SEAT-02 | Add, relabel and remove individual seats | FR-02 | P0 | PARTIALLY IMPLEMENTED (add only; relabel via raw PATCH; removal does not persist) | P2 | A seat with history is deactivated, not hard-deleted. A seat with an active membership or reservation cannot be removed (409). Labels are unique per library. |
| SEAT-03 | Seat states and transitions: Empty → Reserved → Occupied → Empty | FR-02, SRS §3.3 | P0 | PARTIALLY IMPLEMENTED (static field; no transition rules) | P2 | Transitions are enforced server-side. Status is driven by reservations and memberships, not set freely by clients. |
| SEAT-04 | Disabled / maintenance state | F1 §5.1.5, NEW-C, D6 | P1 | NOT IMPLEMENTED | P2 | A `disabled` technical state (documented in SPEC.md). The owner can disable a seat that has no active membership or hold. A disabled seat cannot be booked and is shown in grey. |
| SEAT-05 | Visual seat grid/map showing clear state colours, legend and row grouping | FR-05, NEW-C | P0 | IMPLEMENTED (`SeatGrid.tsx`; read-only status) | P2 | Accessible colours plus text labels, works on mobile. Row and position come from data, not label parsing (P1 refinement). |
| SEAT-06 | Student selects a specific available seat | NEW-C | P0 | PARTIALLY IMPLEMENTED (UI selection only) | P2 | Only bookable seats can be selected. Selecting a seat leads into the booking flow (BOOK-01). |
| SEAT-07 | Owner manual reconciliation / override | SRS §3.2, NEW-C | P0 | PARTIALLY IMPLEMENTED (unrestricted status PATCH) | P2 | The owner can release a stuck reservation or mark a physically occupied seat. Every override requires a reason and writes an audit entry (LOG-06). An override can never silently cancel an active paid membership. |
| SEAT-08 | Live availability counts (total, empty, reserved, occupied) | SRS §3.2, §4.1 | P0 | PARTIALLY IMPLEMENTED (counts from static status) | P2 | Counts reflect expired holds as Empty without manual cleanup. |
| SEAT-09 | Full-day seat model (no per-shift selling) | NEW-D, D1 | P0 | PARTIALLY IMPLEMENTED (the cosmetic shift selector in `SeatGrid.tsx` must be removed) | P2 | A seat holds at most one active membership or hold at a time, for the whole day. The fake shift selector and hardcoded shift hours are removed from the UI. A plan may carry an optional descriptive timing note, which does not affect availability. Per-shift selling is P2 (§4). |

### 3.6 Booking and reservation

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| BOOK-01 | Create booking: seat + plan puts the seat into Reserved hold | FR-06, NEW-D | P0 | NOT IMPLEMENTED (`alert()` placeholder) | P2 | Requires student login. The plan is validated against the library and active state, and the seat must be bookable. Returns the reservation with `expires_at`. |
| BOOK-02 | Double-booking prevention at DB level | SRS §2.5, NFR-02, NEW-C/D | P0 | NOT IMPLEMENTED (no locking anywhere) | P2 | Transaction plus row lock plus a DB constraint. A parallel test on **PostgreSQL** with N concurrent requests for one seat gives exactly 1 success and N−1 409 responses. |
| BOOK-03 | Hold timeout for abandoned unpaid reservations | SRS §3.3, NEW-C | P0 | NOT IMPLEMENTED | P2 | A hold expires after a configurable window (15 min by default, D6). An expired hold is treated as Empty immediately (lazy check) and cleaned up by a scheduled job. |
| BOOK-04 | Student cancels own hold | F1, SPEC §5.3 | P0 | NOT IMPLEMENTED | P2 | Cancelling releases the seat. Only the student who holds it, or the owner, can cancel. |
| BOOK-05 | Prevent invalid or duplicate bookings | NEW-D | P0 | NOT IMPLEMENTED | P2 | Rejected: a seat in another library, a reserved or occupied seat, an inactive plan, a second concurrent hold by the same student in the same library, and a booking while the student already has an active membership at that library (one non-archived membership per student per library, approved default). |
| BOOK-06 | Booking confirmation after verified payment: membership becomes Active and seat becomes Occupied | FR-06, SRS §7.2, NEW-D | P0 | NOT IMPLEMENTED | P3 | Happens only via PAY-03 or PAY-04, atomically. Running it twice has the same effect as once (idempotent). |
| BOOK-07 | Owner approve/reject of online bookings | SRS §4.4, D3 | P2 | NOT IMPLEMENTED | — | D3: no manual approval in the MVP. Verified payment confirms the booking (BOOK-06). The owner keeps control through manual override (SEAT-07) and archival (MEM-06). |

### 3.7 Membership lifecycle

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| MEM-01 | Membership record: student, library, seat, plan, start date, next due date, status | FR-08, NEW-E | P0 | NOT IMPLEMENTED | P3 | `next_due_date = start + plan.duration_days`, computed on the backend only. The plan is referenced by FK. |
| MEM-02 | Statuses Active / Due / Overdue / Archived with automatic transitions | FR-08, SRS Appendix | P0 | NOT IMPLEMENTED | P3 | A daily job moves Active to Due 3 days before `next_due_date`, and Due to Overdue after `next_due_date` (D5). The seat is kept while overdue until the owner archives the member. A successful renewal payment returns the membership to Active. |
| MEM-03 | Student views own memberships (current and past) | SRS §3.1, NEW-B | P0 | NOT IMPLEMENTED | P3 | Shows seat, plan, dates, status and days to due. Only the student's own records are visible. |
| MEM-04 | Owner member list with filters (status, domain, search) and member detail | SRS §4.3, NEW-A | P0 | NOT IMPLEMENTED | P3 | Scoped to the owner's library. Includes online and offline members. Paginated. |
| MEM-05 | Renewal (online by student, offline by owner) | FR-09, SRS §7.3, NEW-A/B | P0 | NOT IMPLEMENTED | P3 | Renewal extends `next_due_date` from the previous `next_due_date` **without** releasing the seat (D5). If the member is more than 15 days overdue, the new period starts from the renewal date (D5 default). Each renewal links to a payment. Renewal history is preserved. |
| MEM-06 | Member archival: archive membership, release seat, keep history | FR-10, SRS §7.4, NEW-E | P0 | NOT IMPLEMENTED | P3 | Atomic: status becomes Archived and the seat becomes Empty. Payments, attendance, complaints and past memberships remain. Requires a reason and is audited. |
| MEM-07 | Membership history preserved (never hard-deleted) | NFR-07, NEW-E | P0 | NOT IMPLEMENTED | P3 | Memberships and payments use protective delete rules. There is no delete endpoint. |
| MEM-08 | Archived members list | SRS §4.3 | P0 | NOT IMPLEMENTED | P3 | The owner can view archived members and their history. |
| MEM-09 | Seat change for an existing member | — | P2 | NOT IMPLEMENTED | — | Not specified in any source. Future. |

### 3.8 Offline students and online/offline identity linking

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| OFF-01 | Owner adds an offline/existing student (name, phone, optional email, domain) | NEW-F, SRS §3.2 | P0 | NOT IMPLEMENTED | P3 | Phone is required and normalised (E.164, India default). If a user with the same normalised phone or email exists, it is linked, never duplicated. A conflicting match (phone matches user X, email matches user Y) is rejected with a clear error. Email is optional, because the claim code (OFF-04) covers students without email. |
| OFF-02 | Offline admission in one step: student + membership + seat + cash payment | NEW-F | P0 | NOT IMPLEMENTED | P3 | One atomic transaction. The seat is locked as in BOOK-02. Audited. |
| OFF-03 | Unified member directory (online and offline) | F1 §5.1.6 | P0 | NOT IMPLEMENTED | P3 | Shown as one list with an "offline" badge. Same record per person. |
| OFF-04 | Offline student claims the account online, without duplicate records | NEW-F, D4 | P0 | NOT IMPLEMENTED | P1 | Registration with a matching normalised phone or email **does not** auto-link. The student proves ownership (D4) with **an email OTP** (if the offline record has an email) **or a one-time claim code** issued by the owner. Codes are single-use, expire, and are attempt-limited. After verification the existing user record becomes an online account and all history becomes visible. Matching is **never** by name. |
| OFF-05 | Duplicate prevention rules | NEW-F | P0 | NOT IMPLEMENTED | P3 | Unique normalised phone and unique email at DB level. Tests cover offline creation followed by online signup, the claim, and the conflicting-match case. |

### 3.9 Payments

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| PAY-01 | Single online payment gateway (Razorpay or Cashfree, evaluated in Phase 2) | FR-07, NEW-G | P0 | BLOCKED (gateway choice in Phase 2; test-mode keys needed before PAY work starts, D2) | P3 | One gateway, used in test mode for development. |
| PAY-02 | Create order server-side using the amount from the plan | NEW-G | P0 | NOT IMPLEMENTED | P3 | The amount always comes from the DB plan price and never from the client. The order is linked to a reservation or renewal. A Pending payment record is created. |
| PAY-03 | Server-side signature verification of the checkout callback | NEW-G, AGENTS §5 | P0 | NOT IMPLEMENTED | P3 | Verified with HMAC-SHA256 against the secret. A forged signature returns 400, logs a security event, and changes nothing. |
| PAY-04 | Webhook handling with signature verification and idempotency | NEW-G | P0 | NOT IMPLEMENTED | P3 | A webhook alone (with the browser closed) confirms the booking. Duplicate or out-of-order webhooks and callbacks produce exactly one success state change. |
| PAY-05 | Handle failed, cancelled and pending payments, and retries | NEW-G | P0 | NOT IMPLEMENTED | P3 | Failed and cancelled payments are recorded and the seat hold is released on expiry. Pending payments are not confirmed. The student can retry while the hold is valid. |
| PAY-06 | Payment record: amount, date, method, status (pending, success, failed) | FR-07 | P0 | NOT IMPLEMENTED | P3 | Gateway IDs are stored. Records are append-only and never deleted. |
| PAY-07 | Owner records offline/cash payment | SRS §3.2, NEW-A/G | P0 | NOT IMPLEMENTED | P3 | Method is cash, UPI-direct or bank transfer. `recorded_by` is set and a unique receipt number is generated. Audited. |
| PAY-08 | Student payment history | SRS §3.1, NEW-B | P0 | NOT IMPLEMENTED | P3 | Only the student's own payments, with receipt details. |
| PAY-09 | Owner payments view (online visibility and offline entries) | NEW-A | P0 | NOT IMPLEMENTED | P3 | All payments for the owner's library, filterable by method, status and date. |
| PAY-10 | Dues: due and overdue members sorted by overdue duration | SRS §3.4, §4.3 | P0 | NOT IMPLEMENTED | P3 | Sorted by days overdue, with contact info. Scoped to the library. |
| PAY-11 | Dues aging buckets (1–7, 8–15, 15+ days) | F1 §5.1.8 | P1 | NOT IMPLEMENTED | P3 | Shown as grouped view of PAY-10. |
| PAY-12 | Downloadable/printable receipt | F1 §5.2.11 | P1 | NOT IMPLEMENTED | P3 | Receipt page per payment. |
| PAY-13 | Fee management model | NEW-A "Fee management", D14 | P0 | NOT IMPLEMENTED | P3 | Dues are derived from membership dates and the plan price (D14). One payment equals one full plan period. No partial payments in the MVP. The amount due is always computed on the backend. |
| PAY-14 | Refunds | — | P2 | NOT IMPLEMENTED | — | Excluded by the brief ("no complex refund system"). Manual refunds are made outside the system. |

### 3.10 Notifications (automatic renewal and expiry)

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| NOT-01 | Daily scheduled job identifying upcoming, due and overdue memberships | FR-09, NEW-H | P0 | NOT IMPLEMENTED | P4 | Runs once a day through the simplest reliable scheduler (Phase 2). Safe to re-run. |
| NOT-02 | In-app notification centre (student and owner) with unread count and mark-read | FR-13, NEW-H | P0 | NOT IMPLEMENTED | P4 | Each user sees only their own notifications. |
| NOT-03 | Renewal-reminder and expiry notifications to student and owner | FR-09, NEW-H | P0 | NOT IMPLEMENTED | P4 | Milestones (D5): 3 days before the due date, on the due date, and when it becomes overdue. The owner receives one daily summary per library rather than one alert per member (F1). |
| NOT-04 | Booking confirmation and payment-received notifications | FR-13 | P0 | NOT IMPLEMENTED | P4 | Sent once per confirmed payment. |
| NOT-05 | Complaint-update and demo-request notifications | FR-13, NEW-J/K | P0 | NOT IMPLEMENTED | P4 | The owner is notified of new complaints and demo requests. The student is notified of status changes. |
| NOT-06 | Deduplication: never send the same milestone twice | NEW-H, AGENTS §6 | P0 | NOT IMPLEMENTED | P4 | A DB unique constraint on (recipient, membership, milestone, date). Running the job 5 times creates 1 notification. |
| NOT-07 | Delivery status record, failure handling, safe retry | NEW-H | P0 | NOT IMPLEMENTED | P4 | Each delivery has a status (pending, sent, failed) with attempts and last error. Failed deliveries are retried on the next run without duplicating successful ones. |
| NOT-08 | Email channel | SRS §1.5, NEW-H, D7 | P1 | NOT IMPLEMENTED | P4 | The same events are emailed through one free-tier provider (chosen in Phase 2), using the delivery log of NOT-07. In-app (P0) works without it. Also used for the OTP in OFF-04. |
| NOT-09 | WhatsApp / SMS | SRS §10.3 | P2 | NOT IMPLEMENTED | — | Not in the first release. |

### 3.11 Attendance (new)

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| ATT-01 | Student check-in | NEW-I | P0 | NOT IMPLEMENTED | P4 | Requires an active, due or overdue (not archived) membership at that library (D8). One open check-in at a time. Stores student, library, membership, date and time. |
| ATT-02 | Student check-out | NEW-I | P0 | NOT IMPLEMENTED | P4 | Closes the open record and computes duration. Checking out with no open check-in returns 400. |
| ATT-03 | Owner views attendance (live "present now" plus history by date or student) | NEW-I | P0 | NOT IMPLEMENTED | P4 | Scoped to the library and paginated. |
| ATT-04 | Student views own attendance history | F1 §5.2.9 | P0 | NOT IMPLEMENTED | P4 | Only the student's own records. |
| ATT-05 | Invalid-operation protection | NEW-I | P0 | NOT IMPLEMENTED | P4 | Rejected: double check-in, check-out without check-in, check-in at another library, check-in by an archived member. Forgotten check-outs are auto-closed by the daily job at the library's closing time, or at end of day if closing time is unset (approved default), and flagged as auto-closed. |
| ATT-06 | Owner manual check-in/out correction | F1 §5.1.10, D8 | P1 | NOT IMPLEMENTED | P4 | The owner can check a student in or out or correct times for their own library. Audited. |
| ATT-07 | QR check-in | F1, SRS §11 (future) | P2 | NOT IMPLEMENTED | — | Future. |

### 3.12 Complaints

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| CMP-01 | Student creates complaint (category + description) | FR-11, NEW-J | P0 | NOT IMPLEMENTED | P4 | Only for a library where the student has or had a membership (approved default). Categories come from a fixed list. |
| CMP-02 | Student views own complaints, status and owner response | FR-11, SRS §7.5 | P0 | NOT IMPLEMENTED | P4 | The student sees only their own complaints. |
| CMP-03 | Owner complaints inbox (filter by status) | SRS §4.3, NEW-J | P0 | NOT IMPLEMENTED | P4 | Scoped to the library. |
| CMP-04 | Owner responds and moves status OPEN → IN_PROGRESS → RESOLVED | FR-11, NEW-J | P0 | NOT IMPLEMENTED | P4 | Transitions are validated. `resolved_at` is set. The student is notified (NOT-05). Audited. |
| CMP-05 | Complaint status report | SRS §8 | P0 | NOT IMPLEMENTED | P4 | Counts by status and category. |
| CMP-06 | Image evidence attachment | NEW-J ("if supported"), D9 | P1 | NOT IMPLEMENTED | P4 | One optional image per complaint, using the same upload rules and storage as PHO-01. Visible only to the student and that library's owner. |

### 3.13 Demo / visit requests (new)

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| DEMO-01 | Student submits demo/visit request (library, preferred date, time slot, note) | NEW-K | P0 | NOT IMPLEMENTED | P2 | Date must be today or later. At most one pending request per student per library. |
| DEMO-02 | Owner demo-request inbox | NEW-K | P0 | NOT IMPLEMENTED | P2 | Scoped to the library and filterable by status. |
| DEMO-03 | Owner accepts or rejects with an optional note | NEW-K | P0 | NOT IMPLEMENTED | P2 | Status PENDING → ACCEPTED / REJECTED. Audited. Student notified. |
| DEMO-04 | Student sees request status | NEW-K | P0 | NOT IMPLEMENTED | P2 | Only the student's own requests. |
| DEMO-05 | Student cancels own pending request | F1 §5.1.11, D10 | P1 | NOT IMPLEMENTED | P2 | Adds a `cancelled` status, set by the student only while the request is pending. No `completed` status in the MVP. |

### 3.14 Dashboards, analytics and reports

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| DASH-01 | Owner dashboard KPIs: total, empty, reserved and occupied seats; active, due and overdue members; today's new bookings; upcoming renewals; pending complaints; pending demo requests; today's check-ins | SRS §4.1, NEW-L | P0 | NOT IMPLEMENTED | P4 | Every number equals the corresponding filtered list. Library-scoped. Tested with two libraries. |
| DASH-02 | Payments / revenue summary (this month, by method) | SRS §8, NEW-L | P0 | NOT IMPLEMENTED | P4 | Counts only successful payments. |
| DASH-03 | Domain-wise member distribution (explore page and owner dashboard) | FR-12 | P0 | PARTIALLY IMPLEMENTED (endpoint + chart; always 0 because there is no Membership) | P4 | Counts active members by domain. Public view shows aggregate counts only. |
| DASH-04 | Occupancy report | SRS §8 | P0 | NOT IMPLEMENTED | P4 | Current occupancy with breakdown. |
| DASH-05 | Dues report | SRS §8 | P0 | NOT IMPLEMENTED | P4 | Same data as PAY-10. |
| DASH-06 | CSV export (members, payments; attendance) | SRS §4.4, §10.2 | P0 | NOT IMPLEMENTED | P4 | Owner-only and library-scoped. Formula injection is escaped. |
| DASH-07 | Student dashboard: active seat, due countdown, renew, check-in button, recent payments, complaints, demo status | NEW-B, F1 §5.2.11 | P0 | NOT IMPLEMENTED | P4 | Only the student's own data, with empty states for new students. |
| DASH-08 | Attendance summary on owner dashboard | NEW-L | P0 | NOT IMPLEMENTED | P4 | Today's check-ins and present now. |
| DASH-09 | Advanced BI, demand prediction | Brief §4 | P2 | — | — | Excluded. |

### 3.15 Logging and audit trail (new, approved after Phase 0)

The application keeps **two kinds of logs** with different purposes:

- **Application (technical) logs:** structured log lines written to standard output and collected by the hosting platform. Used by developers to debug, monitor and investigate incidents.
- **Audit trail (business log):** an append-only database table recording *who did what to which record*. It is part of the product: it supports SRS NFR-07 (auditability) and SRS §2.5 (traceable fee and membership changes), and owners can see their own library's entries.

No extra infrastructure (ELK, Kafka, Redis) is introduced. A hosted error-tracking service is optional (LOG-11).

**Maintenance decision (2026-10-09).** The user asked to drop logging if it is hard to maintain. Assessment: as scoped here it is **low-maintenance** and is kept.
- Application logs go to stdout and the hosting platform stores and rotates them. There is no log server, database or cleanup job to run.
- The audit trail is one DB table written by one shared helper. It needs no scheduled maintenance.
- Everything that does need ongoing upkeep (log server, log shipping, error-tracking account, dashboards) is excluded or left at P2.

If Phase 2 or the implementation finds otherwise, logging is reduced to LOG-01 to LOG-03 plus LOG-06, never silently.

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| LOG-01 | Structured application logging | NEW-LOG, AGENTS §8 | P0 | NOT IMPLEMENTED (no logging config; no `logger` usage) | P1 | Logs are JSON lines on stdout with timestamp, level, logger/module, message, `request_id`, `user_id`, `library_id` and event-specific fields. Levels are configurable by environment variable (DEBUG in dev, INFO in prod). Every backend app uses a module logger. |
| LOG-02 | Request/access logging with correlation ID | NEW-LOG | P0 | NOT IMPLEMENTED | P1 | Each API request logs method, path, status, duration in ms, user ID (if any) and `request_id`. The `request_id` is generated or accepted from a header and returned in an `X-Request-ID` response header, so a user-reported error can be traced. |
| LOG-03 | Error logging | NEW-LOG, AGENTS §8 | P0 | NOT IMPLEMENTED | P1 | Every unhandled exception is logged at ERROR with a stack trace and `request_id`. The client receives only the standard error envelope and the `request_id`, never a stack trace. |
| LOG-04 | Security event logging | NEW-LOG | P0 | NOT IMPLEMENTED | P1 | Logged events: login success and failure (never the password), logout, token refresh failure, 403 permission denials, rate-limit hits, invalid payment signature, invalid webhook signature, account-claim attempts and failures. |
| LOG-05 | Business event logging for critical operations | NEW-LOG, AGENTS §8 | P0 | NOT IMPLEMENTED | P1 | Logged events: reservation created, conflict (409) and expired; payment order created, verified, failed; webhook received and duplicate ignored; offline admission (new vs linked user); archival; scheduled job start and finish with counts processed, sent, skipped and failed. |
| LOG-06 | Persistent audit trail (DB) | NEW-LOG, NFR-07, SRS §2.5 | P0 | NOT IMPLEMENTED | P1 | An append-only `AuditLog` row stores actor, actor role, library, action, entity type and ID, changed fields (before → after), reason (when required), IP, `request_id` and timestamp. **Mandatory for:** library profile and plan changes, seat add, remove, relabel and override, offline admission, membership create, renew, status change and archive, offline payment record, payment status change, complaint status change and response, demo decision, account claim, photo upload and delete. There is no update or delete API, and Django admin is read-only for this model. |
| LOG-07 | Owner activity log view | NEW-LOG | P1 | NOT IMPLEMENTED | P4 | The owner sees audit entries for **their own library only**, filterable by date, action and entity, and paginated. |
| LOG-08 | Sensitive-data redaction | NEW-LOG, security | P0 | NOT IMPLEMENTED | P1 | Never logged: passwords, JWTs, OTP or claim codes, gateway secrets or signatures, full card or bank data. Phone and email are masked in application logs (for example `98******10`). Tests assert that the redaction filter works. |
| LOG-09 | Notification delivery log | NEW-H | P0 | NOT IMPLEMENTED | P4 | Covered by NOT-07 (a delivery record per notification). Listed here so the logging picture is complete. |
| LOG-10 | Log retention | NEW-LOG, D17 | P1 | NOT IMPLEMENTED | P1 | Application logs follow the hosting platform's built-in retention (7 to 30 days, no self-managed storage). Audit trail rows are kept indefinitely in the database. |
| LOG-11 | Hosted error tracking / frontend error reporting | NEW-LOG, D17 | P2 | NOT IMPLEMENTED | — | Not in the MVP, to avoid another service to maintain. |

### 3.16 Cross-cutting quality, deployment and CI/CD

| ID | Feature | Source | Priority | Status | Owner | Acceptance criteria |
|---|---|---|---|---|---|---|
| NFR-01 | Reproducible environment (clean `requirements.txt`, complete `.env.example` files) | AUDIT §16 | P0 | NOT IMPLEMENTED (requirements is a global freeze) | P1 | A fresh clone installs and runs with documented commands. |
| NFR-02 | Secrets and configuration from environment variables only | AGENTS §11 | P0 | NOT IMPLEMENTED (secret key hardcoded) | P1 | No secrets in git. The app refuses to start in production with DEBUG on or a default key. |
| NFR-03 | Responsive UI with loading, error and empty states on every screen | AGENTS §2.3, NFR-05 | P0 | PARTIALLY IMPLEMENTED (3 pages) | Each screen's owner | Works at 375px and at desktop widths. Usable by a non-technical owner. |
| NFR-04 | No fake or mock data in the product | AGENTS §1 | P0 | PARTIALLY IMPLEMENTED (hardcoded amenities, shift hours, `alert()` booking, demo credentials) | P2 | No hardcoded business data in the UI. |
| NFR-05 | Automated tests for every P0 feature (backend) and a frontend build/type check | AGENTS §9 | P0 | PARTIALLY IMPLEMENTED (16 backend tests) | Each feature owner | Concurrency tests run on PostgreSQL. CI runs all tests. |
| NFR-06 | Deployment to production hosting with managed PostgreSQL and object storage | SRS §2.4, NEW-A | P0 | NOT IMPLEMENTED | P1 | Defined in Phase 10 (`DEPLOYMENT.md`). |
| NFR-07 | GitHub CI/CD: PR checks, then merge to main, then automatic deploy | Brief Phase 11 | P0 | NOT IMPLEMENTED | P1 | Defined in Phase 11 (`CI_CD.md`). |
| NFR-08 | Student-facing availability during owner-panel maintenance | NFR-03 (SRS) | P1 | NOT IMPLEMENTED | P1 | Addressed by deployment design. |

---

## 4. Explicitly NOT in MVP (P2 / excluded)

AI recommendations or assistant · exam communities · advanced personalisation · demand prediction · multi-branch or multi-library per owner · platform super admin · drag-and-drop floor-plan editor · waitlist and seat swap · native mobile apps · complex subscription billing · multiple payment gateways · advanced accounting or reconciliation · refund workflow · WhatsApp/SMS infrastructure · per-shift seat selling (D1) · owner approval of online bookings (D3) · partial payments (D14) · phone-number login (D13) · owner verification/invites (D11) · hosted error tracking (D17) · QR or biometric attendance · student–owner chat · microservices, Kubernetes, Kafka, complex Redis · book cataloguing, payroll, canteen (SRS §1.2).

---

## 5. Decisions (approved 2026-10-09)

The recommended defaults were accepted for every open decision. They are now part of the scope above.

| ID | Decision | Approved outcome | Applied in |
|---|---|---|---|
| D1 | Shift-based seat booking | **Full-day seats only.** One active membership or hold per seat. The cosmetic shift selector is removed. Per-shift selling is P2. | SEAT-09, BOOK-01/02, MEM-01, §4 |
| D2 | Payment gateway and keys | Gateway chosen in Phase 2. Test-mode keys are required before PAY work starts. | PAY-01 |
| D3 | Owner approval of online bookings | **No approval.** Verified payment confirms the booking. | BOOK-06, BOOK-07 |
| D4 | Offline-to-online claim verification | **Email OTP** if the offline record has an email, otherwise an **owner-issued one-time claim code**. | OFF-01, OFF-04 |
| D5 | Due and overdue rules | Due = 3 days before `next_due_date`. Overdue = after it. The seat is kept until the owner archives. Renewal extends from the previous due date, or from the renewal date if more than 15 days overdue. | MEM-02, MEM-05, NOT-03 |
| D6 | Hold duration; disabled seat | 15 min, configurable. A `disabled` seat state at P1. | BOOK-03, SEAT-04 |
| D7 | Email notifications | In-app is P0. Email is P1 through one free-tier provider. | NOT-08 |
| D8 | Attendance rules | A non-archived membership is required. Owner correction at P1. | ATT-01, ATT-06 |
| D9 | Complaint image | P1, one optional image. | CMP-06 |
| D10 | Demo statuses | Pending, accepted and rejected (P0), plus student `cancelled` (P1). | DEMO-03, DEMO-05 |
| D11 | Owner registration | Open self-registration, plus publish rules. | AUTH-13, LIB-07 |
| D12 | Library publishing | Auto-publish when the completeness rules are met. | LIB-07 |
| D13 | Phone login | Email login only. | AUTH-14 |
| D14 | Fee model | Dues are derived from membership dates. No partial payments. | PAY-13 |
| D17 | Logging maintenance, retention, error tracking | Logging kept: it is low-maintenance as scoped. Platform retention for app logs; audit rows kept indefinitely; no hosted error tracker. | §3.15 |

Planning items still open (no effect on scope): D15, team member identities and unpushed work (Phase 7); D16, hosting budget and region (Phase 10).

---

## 6. Conflict resolution log

| Conflict | Resolution in this scope |
|---|---|
| Attendance was future scope in the SRS (§11) | Newer approved requirement: **P0** (ATT-01 to ATT-05). QR remains P2. |
| Demo requests and photos are absent from the SRS | Newer approved requirement: **P0**. |
| Shift booking (F1, SPEC) vs no shifts (SRS) | **D1**: full-day seats for the MVP. Per-shift selling is recorded as P2, not dropped silently. |
| Payment gateway fixed as Razorpay (AGENTS, F1, SPEC) vs "evaluate" (brief) | Evaluated in Phase 2 (PAY-01 BLOCKED until then). |
| Owner approve/reject booking (SRS §4.4) vs auto-confirm (brief) | **D3**: auto-confirm on verified payment. Owner control is kept through override and archival. |
| Auto-link offline profile by phone or email (SPEC §6.2) vs "no unsafe matching" (brief) | Auto-link is **rejected**. Verified claim (OFF-04, D4). |
| Logs not specified in the SRS | Added as approved requirement NEW-LOG (§3.15), building on SRS NFR-07 and AGENTS §8. |
| Notification dedup key differs between documents | Recipient + membership + milestone + date (NOT-06). The final schema is set in Phase 3. |
| SPEC payment `refunded` status | Refund workflow excluded (PAY-14). Whether to keep the status value is decided in Phase 3. |
