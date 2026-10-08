# LibraryHive — Entity Relationship Diagram

**Version:** 2.0 (Phase 3). Supersedes v1, which had separate OWNER/STUDENT tables and JSON pricing.
**Date:** 2026-10-09
**Source of truth:** `SPEC.md` v2.0. This diagram shows keys and the main fields only; constraints, indexes and full field lists are in `SPEC.md` §3.

> Project folder structure and API contracts that were in v1 of this file now live in `ARCHITECTURE.md` and (Phase 4) `BACKEND_ARCHITECTURE.md`.

## 1. Full model

```mermaid
erDiagram
    USER ||--o| LIBRARY : "owns (role=owner)"
    USER }o--o| DOMAIN : "prepares for"
    USER ||--o{ ACCOUNT_CLAIM : "claims via"

    LIBRARY }o--o{ DOMAIN : "caters to"
    LIBRARY }o--o{ AMENITY : "offers"
    LIBRARY ||--o{ LIBRARY_PHOTO : "gallery"
    LIBRARY ||--o{ PRICING_PLAN : "offers"
    LIBRARY ||--o{ SEAT : "contains"

    SEAT ||--o{ SEAT_HOLD : "held by"
    USER ||--o{ SEAT_HOLD : "places"
    PRICING_PLAN ||--o{ SEAT_HOLD : "for plan"

    USER ||--o{ MEMBERSHIP : "holds (student)"
    LIBRARY ||--o{ MEMBERSHIP : "has members"
    SEAT ||--o{ MEMBERSHIP : "assigned (history)"
    PRICING_PLAN ||--o{ MEMBERSHIP : "current plan"

    MEMBERSHIP ||--o{ PAYMENT : "paid periods"
    SEAT_HOLD |o--o{ PAYMENT : "first booking"
    USER ||--o{ PAYMENT : "pays"
    LIBRARY ||--o{ PAYMENT : "receives"
    PRICING_PLAN ||--o{ PAYMENT : "priced by"

    USER ||--o{ NOTIFICATION : "receives"
    NOTIFICATION ||--o{ NOTIFICATION_DELIVERY : "email attempts"

    MEMBERSHIP ||--o{ ATTENDANCE_RECORD : "visits"
    USER ||--o{ ATTENDANCE_RECORD : "checks in"
    LIBRARY ||--o{ ATTENDANCE_RECORD : "tracks"

    MEMBERSHIP ||--o{ COMPLAINT : "context"
    USER ||--o{ COMPLAINT : "raises"
    LIBRARY ||--o{ COMPLAINT : "receives"

    USER ||--o{ VISIT_REQUEST : "requests"
    LIBRARY ||--o{ VISIT_REQUEST : "receives"

    LIBRARY ||--o{ AUDIT_LOG : "scope"
    USER ||--o{ AUDIT_LOG : "actor"

    USER {
        uuid id PK
        string name
        string email UK "nullable only for unclaimed offline"
        string phone UK "E.164"
        string role "owner|student"
        uuid domain_id FK
        bool is_offline
        datetime claimed_at
    }
    ACCOUNT_CLAIM {
        uuid id PK
        uuid user_id FK
        string channel "email_otp|owner_code|password_reset"
        string code_hash
        string status "pending|used|expired|revoked"
        datetime expires_at
        int attempts
    }
    DOMAIN {
        uuid id PK
        string code UK
        string name
    }
    AMENITY {
        uuid id PK
        string code UK
        string name
    }
    LIBRARY {
        uuid id PK
        uuid owner_id FK,UK
        string name
        text description
        string address
        string city
        decimal latitude
        decimal longitude
        time opens_at
        time closes_at
        bool is_published
        bool is_active
    }
    LIBRARY_PHOTO {
        uuid id PK
        uuid library_id FK
        string image "object storage key"
        string thumbnail
        bool is_cover "max 1 per library"
        int display_order
    }
    PRICING_PLAN {
        uuid id PK
        uuid library_id FK
        string name
        int duration_days
        decimal price
        string timing_note
        bool is_active
    }
    SEAT {
        uuid id PK
        uuid library_id FK
        string label "unique per library (active)"
        string row_label
        int position
        bool is_active
        bool is_disabled
    }
    SEAT_HOLD {
        uuid id PK
        uuid seat_id FK
        uuid library_id FK
        uuid student_id FK
        uuid plan_id FK
        string kind "booking|owner_manual"
        string status "pending|completed|expired|cancelled|released"
        datetime expires_at
    }
    MEMBERSHIP {
        uuid id PK
        uuid student_id FK
        uuid library_id FK
        uuid seat_id FK
        uuid plan_id FK
        string source "online|offline"
        string state "active|archived"
        date start_date
        date next_due_date
        datetime archived_at
    }
    PAYMENT {
        uuid id PK
        uuid library_id FK
        uuid student_id FK
        uuid membership_id FK
        uuid hold_id FK
        uuid plan_id FK
        string purpose "new_membership|renewal"
        string channel "online|offline"
        string method
        decimal amount
        string status "pending|success|failed|cancelled|needs_refund"
        date period_start
        date period_end
        string gateway_order_id UK
        string gateway_payment_id UK
        string receipt_number UK
        uuid recorded_by_id FK
    }
    PAYMENT_WEBHOOK_EVENT {
        uuid id PK
        string event_id UK
        string event_type
        json payload
        string result
    }
    NOTIFICATION {
        uuid id PK
        uuid recipient_id FK
        uuid library_id FK
        string type
        string dedup_key UK
        datetime read_at
    }
    NOTIFICATION_DELIVERY {
        uuid id PK
        uuid notification_id FK
        string channel "email"
        string status "pending|sent|failed|skipped"
        int attempts
    }
    ATTENDANCE_RECORD {
        uuid id PK
        uuid student_id FK
        uuid library_id FK
        uuid membership_id FK
        uuid seat_id FK
        date date
        datetime check_in_at
        datetime check_out_at
        string status "open|closed|auto_closed"
    }
    COMPLAINT {
        uuid id PK
        uuid student_id FK
        uuid library_id FK
        uuid membership_id FK
        string category
        string status "open|in_progress|resolved"
        text owner_response
        datetime resolved_at
    }
    VISIT_REQUEST {
        uuid id PK
        uuid student_id FK
        uuid library_id FK
        date preferred_date
        string preferred_slot
        string status "pending|accepted|rejected|cancelled"
    }
    AUDIT_LOG {
        uuid id PK
        uuid actor_id FK
        uuid library_id FK
        string action
        string entity_type
        uuid entity_id
        json changes
        string request_id
    }
```

## 2. Key invariants (enforced in the database)

| Invariant | Constraint (SPEC.md) |
|---|---|
| One owner has at most one library | `Library.owner_id` unique (one-to-one) |
| One pending hold per seat | `seathold_one_pending_per_seat` (partial unique) |
| One pending booking hold per student per library | `seathold_one_pending_per_student_library` |
| One active membership per seat (one occupant, D1) | `membership_one_live_per_seat` |
| One active membership per student per library | `membership_one_live_per_student_library` |
| At most one cover photo per library | `libraryphoto_one_cover` |
| No duplicate person | unique normalised `phone`, unique `email` |
| A payment is never confirmed twice | unique `gateway_order_id`, `gateway_payment_id`, webhook `event_id`; row lock in `confirm_payment` |
| No duplicate notification | unique `dedup_key` |
| One open attendance record per student | `attendance_one_open_per_student` |
| One pending visit request per student per library | `visit_one_pending_per_student_library` |

## 3. Derived (not stored) values

| Value | Derived from |
|---|---|
| Seat status (empty / reserved / occupied / disabled) | `Seat.is_disabled`, active `Membership`, live `SeatHold` |
| Membership status (active / due / overdue / archived) | `Membership.state`, `next_due_date`, business date |
| Library capacity | count of active seats |
| Dues | `next_due_date` + current plan price (D14) |
| Renewal history | successful `Payment` rows (`period_start`, `period_end`) |
