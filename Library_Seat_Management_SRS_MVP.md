# Library Seat & Membership Management System — SRS (MVP)

**Document Version:** 0.1 (MVP Draft)  
**Prepared For:** Startup Program — Sitare University (B2B SaaS venture)  
**System Type:** Multi-tenant web application (SaaS) with student + library-owner facing modules  
**Primary Users:** Library Owner/Admin, Student/Member  
**Proposed Stack:** Backend: Django + Django REST Framework · Frontend: Next.js · Database: PostgreSQL · Auth: JWT

## 1. Introduction

### 1.1 Purpose
This SRS defines the requirements for a two-sided web platform that connects students looking for a study seat with libraries/reading rooms that rent seats. The platform gives students visibility into real-time seat availability before they commit, and gives library owners a single system to manage seats, members, fees, renewals, and complaints instead of registers and WhatsApp.

### 1.2 Scope
The MVP covers:
1. A student-facing flow to discover nearby libraries, view live seat maps, register, book a seat, and pay membership fees online.
2. A library-owner-facing admin panel to onboard the library once, then manage seat inventory, members, fees, renewals, complaints, and basic analytics.

Payroll, staff attendance, and inventory beyond seating (e.g. book catalogues) are out of scope for the MVP.

### 1.3 Objectives
- Let a student see exactly how many seats a library has, how many are empty, and which specific seat positions are free or filled.
- Let a student register for a seat and pay membership fees online.
- Give the library owner a one-time setup flow to describe the library and its seating layout.
- Track membership status per student and identify renewal/payment-due cases.
- Archive students when they leave while preserving history.
- Let students raise complaints and owners track and resolve them.
- Show domain-wise member breakdown.
- Let students discover nearby libraries on a map/list and explore their seating system.

### 1.4 Definitions
| Term | Meaning |
|---|---|
| Seat | A single positioned unit of library capacity, e.g. Row A - Seat 3; state can be Empty, Reserved, or Occupied. |
| Reserved Seat | A seat held for a student whose registration/payment is in progress or confirmed but not yet physically occupied. |
| Member | A student whose registration and first payment are confirmed and who is currently assigned an active seat. |
| Domain | The exam/stream a student is preparing for, e.g. UPSC, SSC, NEET, JEE, Board Exams, Other. |
| Owner | The library owner/admin who registers and manages the library. |
| Archived Member | A former member whose record is retained for history but whose seat is released. |
| Due | A pending fee payment or upcoming/lapsed renewal date. |

### 1.5 Assumptions and Constraints
- Each library is operated by one owner account; multi-branch/multi-owner support is future scope.
- Seat layout is a simple positional list (row/label + number), not a drag-and-drop editor.
- Online fee payment requires one gateway such as Razorpay/Cashfree supporting UPI and cards.
- First release targets responsive web; native apps are future scope.
- Reminders can start with email/in-app and later add WhatsApp/SMS.

## 2. Overall Description

### 2.1 Product Perspective
The system is a centralized, multi-tenant platform: many libraries can register independently, each with its own seats, members, and data, while students use one shared app to discover and join any library.

### 2.2 Product Functions
- Library owner onboarding and one-time library profile + seat layout setup.
- Student discovery of nearby libraries with map/list view.
- Live seat map showing empty, reserved, and occupied seats.
- Student registration, seat selection/booking, and online fee payment.
- Membership lifecycle tracking: active, due, renewal, archived.
- Automated renewal and payment-due reminders.
- Complaint submission and resolution tracking.
- Domain-wise analytics.
- Owner dashboard summarizing occupancy, dues, and pending items.

### 2.3 User Classes and Roles
**Library Owner (Admin):** Registers the library, sets up seat layout and pricing, then manages members, seats, fees, renewals, complaints, and reports for their own library.

**Student / Member:** Discovers libraries, views seat maps and domain analytics, registers, books a seat, pays fees, tracks membership/dues, and raises complaints.

**Platform Super Admin:** Future scope.

### 2.4 Operating Environment
- Frontend: Next.js (React), responsive web.
- Backend: Django + Django REST Framework.
- Database: PostgreSQL.
- Authentication: JWT with Owner vs Student RBAC.
- Deployment: cloud VM/PaaS with managed Postgres.

### 2.5 Design and Implementation Constraints
- Seat state changes must be atomic to prevent double assignment.
- Fee payments and membership status changes must be traceable.
- APIs must be library-scoped.
- Seat data model should support a future editable floor plan.

## 3. Functional Requirements

### FR-01 Library Registration & Profile Setup
Owner can create and edit a library profile containing:
- library name
- address
- geo-coordinates
- contact details
- total seat count
- operating hours
- domains catered to
- pricing plans such as monthly/quarterly

### FR-02 Seat Inventory & Layout Setup
Owner can define individual seats using position identifiers such as row/label and number, and add, remove, or relabel seats later. Each seat is exactly one of:
- Empty
- Reserved
- Occupied

### FR-03 Nearby Library Discovery
Students can see nearby libraries using current location or a searched area, with distance, seat availability, and starting price.

### FR-04 Library Explore Page
Students can view a library's full seat map, pricing plans, timings, amenities, and domain-wise member breakdown.

### FR-05 Live Seat Map
Every seat's position and current status are displayed in a visual grid.

### FR-06 Student Registration & Seat Booking
Student selects an available seat and submits a booking. The seat becomes Reserved until payment is confirmed and Occupied after confirmation.

### FR-07 Online Fee Payment
Payment records include amount, date, method, and status: success/failed/pending.

### FR-08 Membership Management
Membership stores plan, seat, start date, next-due date, and status: Active, Due, Overdue, Archived.

### FR-09 Renewal & Due Reminders
System identifies upcoming/overdue renewals and notifies member and owner, at minimum in-app.

### FR-10 Member Archival
Owner can archive a member; their seat becomes Empty while historical fees, tenure, and seat history remain.

### FR-11 Complaint Management
Student submits a categorized complaint with description. Owner can view, respond, and resolve it.

### FR-12 Domain-wise Analytics
Library member counts are grouped by domain/exam and shown on the explore page and owner dashboard.

### FR-13 Notifications
Notify students and owners about booking confirmation, payment received, renewal due, and complaint updates.

## 3.1 Student-Side Requirements
- Browse without an account; registration/login required for booking.
- Prevent booking Reserved or Occupied seats.
- Show active memberships, payment history, and due dates.

## 3.2 Library Owner-Side Requirements
- Show total, occupied, empty, and reserved seats.
- Allow manual seat status changes.
- Allow offline/cash payment recording.

## 3.3 Seat Management Requirements
- Seat transitions follow Empty → Reserved → Occupied → Empty.
- Unpaid Reserved seats should time out after a configurable holding window.

## 3.4 Fees & Renewal Requirements
- Automatically calculate next due date from the selected plan.
- Show Due and Overdue members, sorted by overdue duration.

## 4. Library Owner Panel

### 4.1 Dashboard
Show:
- total seats
- occupied/reserved/empty counts
- active members
- today's new bookings
- overdue payments
- upcoming renewals
- open complaints
- domain-wise member chart

### 4.2 Owner Modules
- Library Profile
- Seat Management
- Member Management
- Fee & Payments
- Renewals & Reminders
- Complaints
- Analytics
- Archive

### 4.3 Owner Pages
- Dashboard
- Library Profile & Setup
- Seat Map / Layout Manager
- Members List & Member Detail
- Payments & Dues
- Complaints Inbox
- Analytics
- Archived Members

### 4.4 Owner Actions
- Complete/edit library and seat setup.
- Approve/reject booking and override seat status.
- Record online/manual payments.
- Send renewal/due reminders.
- Archive members and free seats.
- Respond to/close complaints.
- Export basic member/payment reports as CSV.

### 4.5 Access Control
- Owner: full access to their own library data.
- Student: own profile, bookings, payments, complaints, plus public browse/explore access.

## 5. Data Requirements

### 5.1 Core Entities
- **Library:** profile, geo-location, timings, pricing plans, owner mapping.
- **Seat:** position/label, library mapping, current status.
- **Student:** personal details, login credentials, domain.
- **Membership:** student-library-seat relationship, plan, status, dates.
- **Payment:** payment attempt/record, amount, method, status, timestamp.
- **Complaint:** category, description, status, resolution notes.
- **Notification/Reminder:** reminder scheduling/delivery status.

### 5.2 Suggested Data Fields
**Library:** library_id, owner_id, name, address, latitude, longitude, total_seats, timings, domains_catered, created_at.

**Seat:** seat_id, library_id, label/position, status.

**Student:** student_id, name, email, phone, domain, created_at.

**Membership:** membership_id, student_id, library_id, seat_id, plan, start_date, next_due_date, status.

**Payment:** payment_id, membership_id, amount, method, status, paid_at.

**Complaint:** complaint_id, student_id, library_id, category, description, status, created_at, resolved_at.

## 6. Non-Functional Requirements

| Requirement | Description |
|---|---|
| NFR-01 Security | Role-based access control; owner can access only their own library data; passwords/JWTs handled securely. |
| NFR-02 Data Integrity | Seat status changes must be atomic. |
| NFR-03 Availability | Student-facing discovery and booking should remain usable during owner-panel maintenance. |
| NFR-04 Performance | Seat map and library lists should load quickly with pagination/filtering as data grows. |
| NFR-05 Usability | Owner panel should be usable by a non-technical owner. |
| NFR-06 Scalability | Multi-tenant model should support many libraries and students. |
| NFR-07 Auditability | Payment and membership changes retain history. |
| NFR-08 Maintainability | Seat, membership, and payment modules remain separable for parallel team development. |

## 7. Primary Workflows

### 7.1 Library Owner Onboarding
1. Owner registers and creates library profile.
2. Owner sets up seat layout and pricing plans.
3. Library becomes visible to students.
4. Owner manages seats, members, payments, and complaints.

### 7.2 Student Discovery & Seat Booking
1. Student opens app and sees nearby libraries.
2. Student explores a library.
3. Student selects an available seat; it becomes Reserved.
4. Student registers and pays.
5. Successful payment creates membership and changes seat to Occupied.

### 7.3 Renewal & Due Handling
1. System checks active memberships daily.
2. Reminder is sent as due date approaches.
3. Student renews and pays.
4. Next due date is recalculated.
5. Unpaid memberships become Overdue.

### 7.4 Member Exit / Archival
1. Membership is marked as ending.
2. Owner confirms exit.
3. Membership becomes Archived.
4. Seat becomes Empty.
5. Historical tenure/payment data remains.

### 7.5 Complaint Handling
1. Student submits complaint.
2. Owner sees it in Complaints Inbox and responds.
3. Owner resolves it.
4. Student sees resolution status.

## 8. Reporting Requirements
- Occupancy report.
- Dues report.
- Domain-wise member distribution.
- Payment/revenue summary.
- Complaint status report.

## 9. Acceptance Criteria
- Student can find a nearby library and see its live seat map.
- Student can register, book a specific seat, and pay online.
- System never allows two students to hold the same seat.
- Owner can complete setup once and manage the library afterward.
- Owner can see due/overdue renewals.
- Archiving frees the seat while retaining history.
- Student can submit a complaint and later see it resolved.

## 10. MVP Scope Recommendation

### 10.1 Build First
- Owner onboarding + one-time seat layout setup.
- Nearby library discovery + explore page.
- Live seat map + no-double-booking.
- Online first-fee payment + membership.
- Owner dashboard with occupancy + dues and manual overrides.
- Member archival.
- Basic complaint submission/resolution.

### 10.2 Add Next
- Automated renewal/due reminders via email/WhatsApp/SMS; start with in-app + email.
- Domain-wise analytics.
- CSV export.
- Seat-hold timeout.

### 10.3 Defer
- Platform Super Admin.
- Multi-branch libraries.
- Drag-and-drop floor plan.
- Waitlist.
- In-house WhatsApp/SMS gateway selection.

### 10.4 Four-Person Team Split
| Person | Responsibility |
|---|---|
| Person A | Owner onboarding & library profile: FR-01, FR-02, owner setup flow. |
| Person B | Discovery & seat map: FR-03, FR-04, FR-05, student browse/explore/seat-map UI. |
| Person C | Booking, payments & membership: FR-06, FR-07, FR-08, FR-09, payment gateway. |
| Person D | Owner dashboard, complaints & analytics: FR-10, FR-11, FR-12, owner dashboard and reports. |

The API contract and PostgreSQL schema should be agreed upon before parallel implementation.

## 11. Future Scope
- Waitlist and seat-swap requests.
- Platform-level Super Admin.
- Multi-branch libraries.
- In-app student-owner chat.
- QR attendance/check-in.
- Native mobile apps.

## Appendix
- **Seat statuses:** Empty, Reserved, Occupied.
- **Membership statuses:** Active, Due, Overdue, Archived.
- **Complaint statuses:** Open, In Progress, Resolved.
- **Payment statuses:** Pending, Success, Failed.
