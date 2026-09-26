1. ER Diagram
erDiagram
    LIBRARY ||--o{ SEAT : "has"
    LIBRARY ||--o{ MEMBERSHIP : "has"
    LIBRARY ||--o{ COMPLAINT : "receives"
    LIBRARY }o--|| OWNER : "owned by"
    STUDENT ||--o{ MEMBERSHIP : "holds"
    STUDENT ||--o{ COMPLAINT : "raises"
    MEMBERSHIP ||--o{ PAYMENT : "generates"
    MEMBERSHIP ||--|| SEAT : "assigned"

    OWNER {
        uuid id PK
        string name\

        string email
        string phone
        datetime created_at
    }

    LIBRARY {
        uuid id PK
        uuid owner_id FK
        string name
        string address
        float latitude
        float longitude
        int total_seats
        json timings
        json domains_catered
        json pricing_plans
        datetime created_at
    }

    SEAT {
        uuid id PK
        uuid library_id FK
        string label
        string status "empty|reserved|occupied"
        datetime updated_at
    }

    STUDENT {
        uuid id PK
        string name
        string email
        string phone
        string domain "UPSC|SSC|NEET|JEE|other"
        datetime created_at
    }

    MEMBERSHIP {
        uuid id PK
        uuid student_id FK
        uuid library_id FK
        uuid seat_id FK
        string plan
        date start_date
        date next_due_date
        string status "active|due|overdue|archived"
        datetime created_at
    }

    PAYMENT {
        uuid id PK
        uuid membership_id FK
        decimal amount
        string method "upi|card|cash"
        string status "pending|success|failed"
        datetime paid_at
    }

    COMPLAINT {
        uuid id PK
        uuid student_id FK
        uuid library_id FK
        string category
        text description
        string status "open|in_progress|resolved"
        datetime created_at
        datetime resolved_at
    }
Key constraints to enforce at DB/app level:

Seat.status transition strictly: empty → reserved → occupied → empty. Wrap the reserve/confirm step in a DB transaction (select_for_update in Django) so two students can't grab the same seat.
One Seat maps to at most one active Membership at a time.
Payment.status = success is what triggers Seat: reserved → occupied and Membership: created/active.
2. Project Folder Structure
library-seat-mgmt/
├── backend/                         # Django + DRF
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/                      # project settings
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── apps/
│       ├── core/                    # shared: permissions, base models, utils
│       │   ├── permissions.py       # IsOwner, IsStudent, IsLibraryOwnerOf
│       │   └── models.py            # BaseModel (uuid, created_at)
│       ├── accounts/                # Owner + Student auth (JWT)
│       │   ├── models.py
│       │   ├── serializers.py
│       │   ├── views.py
│       │   └── urls.py
│       ├── libraries/               # Person A
│       │   ├── models.py            # Library
│       │   ├── serializers.py
│       │   ├── views.py
│       │   └── urls.py
│       ├── seats/                   # Person B
│       │   ├── models.py            # Seat
│       │   ├── serializers.py
│       │   ├── views.py
│       │   └── urls.py
│       ├── memberships/             # Person C
│       │   ├── models.py            # Membership
│       │   ├── serializers.py
│       │   ├── views.py
│       │   └── urls.py
│       ├── payments/                # Person C
│       │   ├── models.py            # Payment
│       │   ├── gateway.py           # Razorpay/Cashfree wrapper
│       │   ├── serializers.py
│       │   ├── views.py
│       │   └── urls.py
│       └── complaints/              # Person D
│           ├── models.py            # Complaint
│           ├── serializers.py
│           ├── views.py
│           └── urls.py
│
├── frontend/                        # Next.js
│   ├── package.json
│   ├── .env.local.example
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── student/                 # Person B + C screens
│   │   │   ├── discover/
│   │   │   ├── library/[id]/        # explore page, seat map
│   │   │   ├── dashboard/
│   │   │   └── complaints/
│   │   └── owner/                   # Person A + D screens
│   │       ├── setup/
│   │       ├── dashboard/
│   │       ├── seats/
│   │       ├── members/
│   │       ├── payments/
│   │       ├── complaints/
│   │       └── analytics/
│   ├── components/
│   │   ├── seat-map/
│   │   ├── ui/
│   │   └── charts/
│   └── lib/
│       ├── api-client.ts            # fetch wrapper hitting backend, shared by everyone
│       └── types.ts                 # shared TS types matching API contract below
│
├── docker-compose.yml               # postgres + backend + frontend
└── README.md
3. API Contract (v0.1 — freeze this before splitting work)
Base URL: /api/v1/. Auth: JWT in Authorization: Bearer <token>. Owner and student endpoints are role-checked; owner endpoints are further scoped to request.user.library.

Method	Endpoint	Role	Description
POST	/auth/register/student/	Public	Student signup
POST	/auth/register/owner/	Public	Owner signup
POST	/auth/login/	Public	Returns JWT access + refresh
POST	/auth/refresh/	Public	Refresh token
GET	/libraries/	Public	List/search nearby libraries (lat, lng, radius query params)
GET	/libraries/{id}/	Public	Library explore page: profile, pricing, timings, domain breakdown
POST	/libraries/	Owner	Create library profile (one-time onboarding)
PATCH	/libraries/{id}/	Owner	Edit library profile
GET	/libraries/{id}/seats/	Public	Live seat map (all seats + status)
POST	/libraries/{id}/seats/	Owner	Add seat(s) during setup
PATCH	/seats/{id}/	Owner	Manually override seat status
POST	/seats/{id}/reserve/	Student	Reserve a seat (starts booking; seat → reserved)
POST	/memberships/	Student	Confirm registration for a reserved seat
GET	/memberships/mine/	Student	Own membership(s), status, next due date
GET	/memberships/	Owner	List memberships for owner's library (filter by status)
PATCH	/memberships/{id}/archive/	Owner	Archive member, free seat
POST	/payments/	Student	Initiate payment for a membership
POST	/payments/webhook/	Gateway	Payment gateway callback → updates payment + seat + membership status
POST	/payments/{id}/offline/	Owner	Record a manual/cash payment
GET	/payments/dues/	Owner	List due/overdue members, sorted by days overdue
POST	/complaints/	Student	Raise a complaint
GET	/complaints/	Owner	List complaints for owner's library
PATCH	/complaints/{id}/	Owner	Respond / mark resolved
GET	/analytics/domain-breakdown/	Public/Owner	Domain-wise member count for a library
GET	/analytics/dashboard/	Owner	Occupancy, dues, complaints summary
Response shape convention (keep consistent everywhere):

{
  "success": true,
  "data": { },
  "error": null
}