"""Platform-wide usage figures for the LibraryHive team (internal dashboard, not tenant-scoped).

Every figure is an aggregate computed in PostgreSQL; no student or owner personal data is returned.

Definitions (shown to the team on the dashboard too):

* **Booking** = one `Membership` row. A membership only exists after a successful payment (online) or an owner
  admission (offline), so every row is a real, confirmed seat booking. Renewals extend an existing membership
  and are counted separately (successful renewal payments), never as new bookings. Archived memberships are
  still bookings that happened, so they stay in "total bookings".
* **Booking date** = `Membership.created_at` in the business time zone (Asia/Kolkata).
* **Unique booking students** = `COUNT(DISTINCT student_id)` over bookings.
* **Monthly active students** = unique students with a booking created in the current calendar month.
* **Repeat booking %** = of the students who booked in the range, the share that have more than one booking
  in total (any library, any time).
* **Acquired through LibraryHive** = distinct students holding an `online`-source booking at that library.
* **Attendance** = `AttendanceRecord` rows (a check-in), reported as check-ins and distinct students.
* **Abandoned holds** = booking holds (kind `booking`) that ended `cancelled` or `expired` without payment.
  A hold behind a pending or approved direct UPI claim is not abandoned (the owner may still approve it); pending
  claims are reported as `awaiting_upi_review`.
  There is no "cancel a paid booking" action in the product, so paid-booking cancellation does not exist;
  archived memberships (the owner ending a tenure) are reported separately.

Cross-app note: ARCHITECTURE.md 8.2 asks for cross-app reads through selectors. Platform aggregates span six
apps and are read-only, so they live here in one reviewed module instead of six one-off selectors.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.db.models import Count, DecimalField, IntegerField, OuterRef, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.core.dates import business_today
from apps.libraries.models import Library
from apps.memberships.models import Membership
from apps.payments.models import Payment, UpiPaymentRequest
from apps.seats.models import SeatHold

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
GRANULARITIES = ("day", "week", "month")

# What the current data model cannot answer, with the reason. Sent to the dashboard so gaps are visible.
UNAVAILABLE = [
    {
        "key": "subscription_plan",
        "label": "Library subscription plan and status",
        "reason": "LibraryHive has no subscription model for libraries yet. Pricing plans in the product are "
        "the fees libraries charge their own students.",
    },
    {
        "key": "plan_limits",
        "label": "Libraries approaching plan limits",
        "reason": "There are no LibraryHive plan limits to compare against.",
    },
    {
        "key": "platform_revenue",
        "label": "Subscription revenue, MRR and revenue by plan",
        "reason": "No payment records exist for library subscriptions. Payments in the database are students "
        "paying libraries, which is not LibraryHive revenue.",
    },
]


# --- date helpers ----------------------------------------------------------------------------------------


def _start_of(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min))


def bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Aware [start, end + 1 day) so `end` is inclusive and index-friendly range filters can be used."""
    return _start_of(start), _start_of(end + timedelta(days=1))


def default_range(today: date | None = None) -> tuple[date, date]:
    today = today or business_today()
    return today - timedelta(days=DEFAULT_RANGE_DAYS - 1), today


def _in_range(field: str, start: date, end: date) -> Q:
    lo, hi = bounds(start, end)
    return Q(**{f"{field}__gte": lo, f"{field}__lt": hi})


def _bookings(start: date | None = None, end: date | None = None) -> QuerySet[Membership]:
    queryset = Membership.objects.all()
    if start and end:
        queryset = queryset.filter(_in_range("created_at", start, end))
    return queryset


def _distinct_students(queryset: QuerySet) -> int:
    return queryset.values("student_id").distinct().count()


# --- overview --------------------------------------------------------------------------------------------


def overview(*, today: date | None = None) -> dict:
    """Platform overview cards (all time, except monthly active)."""
    today = today or business_today()
    month_start = today.replace(day=1)
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True)
    libraries = Library.objects.all()
    bookings = _bookings()
    return {
        "as_of": today.isoformat(),
        "students": {
            # Self-registered accounts. Offline walk-ins are created by owners and counted separately.
            "registered": students.filter(is_offline=False).count(),
            "offline_walk_ins": students.filter(is_offline=True).count(),
        },
        "libraries": {
            "registered": libraries.count(),
            "published": libraries.filter(is_published=True, is_active=True).count(),
            # Active = at least one live (active-state) membership right now.
            "active": libraries.filter(memberships__state=Membership.State.ACTIVE).distinct().count(),
        },
        "bookings": {
            "total": bookings.count(),
            "online": bookings.filter(source=Membership.Source.ONLINE).count(),
            "offline": bookings.filter(source=Membership.Source.OFFLINE).count(),
            "unique_students": _distinct_students(bookings),
            "monthly_active_students": _distinct_students(_bookings(month_start, today)),
        },
    }


# --- bookings --------------------------------------------------------------------------------------------


def _bucket_start(day: date, granularity: str) -> date:
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    return day


def _next_bucket(day: date, granularity: str) -> date:
    if granularity == "week":
        return day + timedelta(days=7)
    if granularity == "month":
        return (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return day + timedelta(days=1)


def booking_trend(start: date, end: date, granularity: str) -> list[dict]:
    """Bookings per day, week (Monday start) or month, zero-filled so a quiet day still shows as 0."""
    trunc = {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}[granularity]
    rows = (
        _bookings(start, end)
        .annotate(bucket=trunc("created_at"))
        .values("bucket")
        .annotate(bookings=Count("id"), students=Count("student_id", distinct=True))
        .order_by("bucket")
    )
    found = {(row["bucket"].date() if isinstance(row["bucket"], datetime) else row["bucket"]): row for row in rows}
    series, cursor = [], _bucket_start(start, granularity)
    while cursor <= end:
        row = found.get(cursor)
        series.append(
            {
                "date": cursor.isoformat(),
                "bookings": row["bookings"] if row else 0,
                "unique_students": row["students"] if row else 0,
            }
        )
        cursor = _next_bucket(cursor, granularity)
    return series


def library_distribution(start: date, end: date, *, limit: int = 10) -> list[dict]:
    rows = (
        _bookings(start, end)
        .values("library_id", "library__name")
        .annotate(bookings=Count("id"), students=Count("student_id", distinct=True))
        .order_by("-bookings", "library__name")[:limit]
    )
    return [
        {
            "library_id": str(r["library_id"]),
            "name": r["library__name"],
            "bookings": r["bookings"],
            "unique_students": r["students"],
        }
        for r in rows
    ]  # fmt: skip


def booking_analytics(start: date, end: date, granularity: str = "day", *, today: date | None = None) -> dict:
    today = today or business_today()
    in_range = _bookings(start, end)
    range_students = in_range.values("student_id")

    unique_students = _distinct_students(in_range)
    repeat_students = (
        Membership.objects.filter(student_id__in=range_students)
        .values("student_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .count()
    )
    in_range_holds = SeatHold.objects.filter(kind=SeatHold.Kind.BOOKING).filter(_in_range("created_at", start, end))
    # A hold behind a pending or approved direct UPI claim is not abandoned: the student says they paid and the owner
    # is still deciding (pending) or did decide yes (approved; its membership is a booking). Such a hold is left out of
    # the abandoned count and the pending ones are reported separately. A rejected or cancelled claim is abandoned.
    claimed = UpiPaymentRequest.objects.filter(
        hold__isnull=False, status__in=[UpiPaymentRequest.Status.PENDING, UpiPaymentRequest.Status.APPROVED]
    ).values("hold_id")
    awaiting_upi_review = in_range_holds.filter(
        pk__in=UpiPaymentRequest.objects.filter(status=UpiPaymentRequest.Status.PENDING, hold__isnull=False).values(
            "hold_id"
        )
    ).count()
    holds = in_range_holds.exclude(Q(pk__in=claimed) & ~Q(status=SeatHold.Status.COMPLETED))
    hold_counts = {row["status"]: row["n"] for row in holds.values("status").annotate(n=Count("id"))}
    # A pending hold past its expiry is dead on every read (SPEC 3.9) even before the cleanup job marks it
    # `expired`, so it is abandoned, not "still pending".
    lapsed = holds.filter(status=SeatHold.Status.PENDING, expires_at__lte=timezone.now()).count()
    still_pending = hold_counts.get("pending", 0) - lapsed
    abandoned = hold_counts.get("cancelled", 0) + hold_counts.get("expired", 0) + lapsed
    finished = hold_counts.get("completed", 0) + abandoned

    week_start = today - timedelta(days=today.weekday())
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "granularity": granularity,
        "today": _bookings(today, today).count(),
        "this_week": _bookings(week_start, today).count(),
        "this_month": _bookings(today.replace(day=1), today).count(),
        "in_range": {
            "bookings": in_range.count(),
            "online": in_range.filter(source=Membership.Source.ONLINE).count(),
            "offline": in_range.filter(source=Membership.Source.OFFLINE).count(),
            "unique_students": unique_students,
            "repeat_students": repeat_students,
            "repeat_booking_percent": round(100 * repeat_students / unique_students, 1) if unique_students else None,
            "renewals": Payment.objects.filter(purpose=Payment.Purpose.RENEWAL, status=Payment.Status.SUCCESS)
            .filter(_in_range("paid_at", start, end))
            .count(),
            "archived_memberships": Membership.objects.filter(_in_range("archived_at", start, end)).count(),
            "check_ins": AttendanceRecord.objects.filter(date__gte=start, date__lte=end).count(),
            "students_checked_in": AttendanceRecord.objects.filter(date__gte=start, date__lte=end)
            .values("student_id")
            .distinct()
            .count(),
        },
        "holds": {
            "completed": hold_counts.get("completed", 0),
            "cancelled": hold_counts.get("cancelled", 0),
            "expired": hold_counts.get("expired", 0) + lapsed,
            "still_pending": still_pending,
            "awaiting_upi_review": awaiting_upi_review,
            "abandoned": abandoned,
            "abandoned_percent": round(100 * abandoned / finished, 1) if finished else None,
        },
        "trend": booking_trend(start, end, granularity),
        "by_library": library_distribution(start, end),
    }


# --- library performance ---------------------------------------------------------------------------------

LIBRARY_ORDERINGS = {
    "bookings": "bookings_in_range",
    "total_bookings": "total_bookings",
    "members": "registered_members",
    "active_members": "active_members",
    "online_students": "online_students",
    "check_ins": "check_ins_in_range",
    "name": "name",
}


def library_performance(start: date, end: date, *, search: str = "", ordering: str = "-bookings") -> QuerySet[Library]:
    """One row per library. Counts come from the memberships join only (COUNT DISTINCT / FILTER) and
    attendance from a correlated subquery, so a library with many check-ins cannot multiply its booking count.
    """
    check_ins = (
        AttendanceRecord.objects.filter(library=OuterRef("pk"), date__gte=start, date__lte=end)
        .order_by()
        .values("library")
        .annotate(n=Count("id"))
        .values("n")
    )
    queryset = Library.objects.annotate(
        registered_members=Count("memberships__student", distinct=True),
        active_members=Count("memberships", filter=Q(memberships__state=Membership.State.ACTIVE), distinct=True),
        online_students=Count(
            "memberships__student", filter=Q(memberships__source=Membership.Source.ONLINE), distinct=True
        ),
        total_bookings=Count("memberships", distinct=True),
        bookings_in_range=Count("memberships", filter=_in_range("memberships__created_at", start, end), distinct=True),
        unique_students_in_range=Count(
            "memberships__student", filter=_in_range("memberships__created_at", start, end), distinct=True
        ),
        check_ins_in_range=Coalesce(Subquery(check_ins, output_field=IntegerField()), 0),
    )
    if search.strip():
        queryset = queryset.filter(Q(name__icontains=search.strip()) | Q(city__icontains=search.strip()))
    descending = ordering.startswith("-")
    field = LIBRARY_ORDERINGS.get(ordering.lstrip("-"), "bookings_in_range")
    return queryset.order_by(f"-{field}" if descending else field, "name", "id")


def library_row(library: Library) -> dict:
    return {
        "id": str(library.pk),
        "name": library.name,
        "city": library.city,
        "is_published": library.is_published,
        "registered_members": library.registered_members,
        "active_members": library.active_members,
        "online_students": library.online_students,
        "total_bookings": library.total_bookings,
        "bookings_in_range": library.bookings_in_range,
        "unique_students_in_range": library.unique_students_in_range,
        "check_ins_in_range": library.check_ins_in_range,
        # No LibraryHive subscription data exists (see UNAVAILABLE).
        "subscription_plan": None,
        "subscription_status": None,
    }


# --- subscriptions and revenue ---------------------------------------------------------------------------


def subscription_analytics(start: date, end: date) -> dict:
    """Only what the data supports. Per-library averages are over all registered libraries."""
    library_count = Library.objects.count()
    in_range = _bookings(start, end)
    bookings = in_range.count()
    students = _distinct_students(in_range)
    # Unique students per library, summed, then averaged: one student at two libraries counts at both.
    pairs = in_range.values("library_id", "student_id").distinct().count()
    online = Payment.objects.filter(channel=Payment.Channel.ONLINE).filter(_in_range("created_at", start, end))
    ok = online.filter(status=Payment.Status.SUCCESS)
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "libraries": library_count,
        "averages_per_library": {
            "bookings": round(bookings / library_count, 2) if library_count else None,
            "unique_booking_students": round(pairs / library_count, 2) if library_count else None,
        },
        "platform_unique_students": students,
        # Student fees paid online to libraries. NOT LibraryHive revenue; shown only as a payment-health signal.
        "student_payments_online": {
            "successful": ok.count(),
            "failed": online.filter(status=Payment.Status.FAILED).count(),
            "cancelled": online.filter(status=Payment.Status.CANCELLED).count(),
            "pending": online.filter(status=Payment.Status.PENDING).count(),
            "needs_refund": online.filter(status=Payment.Status.NEEDS_REFUND).count(),
            "amount_successful": str(
                ok.aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField()))["total"]
            ),
            "is_platform_revenue": False,
        },
        "unavailable": UNAVAILABLE,
    }
