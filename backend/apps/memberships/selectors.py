"""Read-side queries for memberships (BACKEND_ARCHITECTURE.md section 8, SPEC.md 3.10).

Other apps read membership facts only through these functions, never through
the model, so the status rules live in one place.
"""

import math
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Case, CharField, Exists, OuterRef, Q, QuerySet, Value, When

from apps.core.dates import business_today
from apps.core.search import phone_digits

from .models import Membership

ACTIVE = "active"
DUE = "due"
OVERDUE = "overdue"
ARCHIVED = "archived"


def annotate_status(queryset: QuerySet[Membership], *, today: date | None = None) -> QuerySet[Membership]:
    """Add `status`: archived, overdue, due or active, computed in SQL (decision D5).

    "Today" is the Asia/Kolkata business date. A membership is due from three
    days before `next_due_date` up to and including that date, and overdue the
    day after.
    """
    today = today or business_today()
    due_from = today + timedelta(days=settings.MEMBERSHIP_DUE_WINDOW_DAYS)
    return queryset.annotate(
        status=Case(
            When(state=Membership.State.ARCHIVED, then=Value(ARCHIVED)),
            When(next_due_date__lt=today, then=Value(OVERDUE)),
            When(next_due_date__lte=due_from, then=Value(DUE)),
            default=Value(ACTIVE),
            output_field=CharField(),
        )
    )


def active_membership_exists(seat) -> bool:
    """True if the seat has a non-archived membership: it is *occupied* (SPEC.md 4.1 rule 2).

    Called by `seats` (imported lazily there, so `seats` never imports memberships models) and by
    every writer of seat availability inside its seat lock.
    """
    return Membership.objects.filter(seat=seat, state=Membership.State.ACTIVE).exists()


def student_is_member(student, library) -> bool:
    """True if the student holds a non-archived membership at the library (ALREADY_MEMBER check)."""
    return Membership.objects.filter(student=student, library=library, state=Membership.State.ACTIVE).exists()


def current_membership(student, library) -> Membership | None:
    """The student's non-archived membership at the library with its derived `status`, or None."""
    return annotate_status(
        Membership.objects.filter(student=student, library=library, state=Membership.State.ACTIVE)
    ).first()


def occupied_expression(seat_ref: str = "pk") -> Exists:
    """An `EXISTS` expression: the outer seat has a non-archived membership (it is occupied, SPEC.md 4.1 rule 2).

    Lets `seats` derive the status of a whole library in one query without importing the model.
    """
    return Exists(Membership.objects.filter(seat=OuterRef(seat_ref), state=Membership.State.ACTIVE))


def active_occupants(seat_ids) -> dict:
    """{seat_id: {"membership_id", "student_name"}} for the non-archived memberships on these seats.

    Owner-only detail: the public seat map never shows who sits where (SPEC.md 4.1).
    """
    rows = Membership.objects.filter(seat_id__in=list(seat_ids), state=Membership.State.ACTIVE).select_related(
        "student"
    )
    return {row.seat_id: {"membership_id": row.pk, "student_name": row.student.name} for row in rows}


# --- Owner and student views of memberships (#49-#51, #56, #57) -------------------------------------------------

DUE_BUCKETS = {"1-7": (1, 7), "8-15": (8, 15), "15+": (16, None)}
MEMBER_STATUSES = (ACTIVE, DUE, OVERDUE, ARCHIVED)


def _with_status(queryset: QuerySet[Membership]) -> QuerySet[Membership]:
    return annotate_status(queryset.select_related("student__domain", "seat", "plan", "library"))


def owner_members(
    library,
    *,
    status: str | None = None,
    domain: str | None = None,
    source: str | None = None,
    search: str | None = None,
) -> QuerySet[Membership]:
    """The unified member directory of one library (#50). `current` (the default) is everyone not archived."""
    queryset = _with_status(Membership.objects.filter(library=library))
    if status in MEMBER_STATUSES:
        queryset = queryset.filter(status=status)
    else:
        queryset = queryset.filter(state=Membership.State.ACTIVE)
    if domain:
        queryset = queryset.filter(student__domain__code=domain)
    if source:
        queryset = queryset.filter(source=source)
    if search:
        digits = phone_digits(search)
        match = Q(student__name__icontains=search) | Q(seat__label__icontains=search)
        if digits:
            match |= Q(student__phone__contains=digits)
        queryset = queryset.filter(match)
    return queryset.order_by("student__name", "pk")


def owner_member(library, membership_id) -> Membership | None:
    """One membership of the owner's library with its derived status, or None (404)."""
    return _with_status(Membership.objects.filter(library=library, pk=membership_id)).first()


def other_memberships_here(membership: Membership) -> QuerySet[Membership]:
    """The student's other tenures at the same library, newest first (history, SPEC.md 4.4)."""
    return _with_status(
        Membership.objects.filter(library_id=membership.library_id, student_id=membership.student_id).exclude(
            pk=membership.pk
        )
    ).order_by("-start_date")


def student_memberships(student, *, include_archived: bool = False) -> QuerySet[Membership]:
    queryset = _with_status(Membership.objects.filter(student=student))
    if not include_archived:
        queryset = queryset.filter(state=Membership.State.ACTIVE)
    return queryset.order_by("-start_date", "pk")


def student_membership(student, membership_id) -> Membership | None:
    return _with_status(Membership.objects.filter(student=student, pk=membership_id)).first()


def owner_dues(
    library, *, status: str | None = None, bucket: str | None = None, today: date | None = None
) -> QuerySet[Membership]:
    """Due and overdue members (#49), most overdue first. Derived from `next_due_date` (D14), never stored."""
    today = today or business_today()
    queryset = _with_status(Membership.objects.filter(library=library)).filter(status__in=(DUE, OVERDUE))
    if status in (DUE, OVERDUE):
        queryset = queryset.filter(status=status)
    if bucket in DUE_BUCKETS:
        low, high = DUE_BUCKETS[bucket]
        queryset = queryset.filter(next_due_date__lte=today - timedelta(days=low))
        if high is not None:
            queryset = queryset.filter(next_due_date__gte=today - timedelta(days=high))
    return queryset.order_by("next_due_date", "pk")


def days_overdue(membership: Membership, *, today: date | None = None) -> int:
    return max(0, ((today or business_today()) - membership.next_due_date).days)


def amount_due(membership: Membership, *, today: date | None = None):
    """Current plan price x the periods overdue, at least one (#49)."""
    periods = max(1, math.ceil(days_overdue(membership, today=today) / membership.plan.duration_days))
    return membership.plan.price * periods


def renewal_open(membership: Membership, *, today: date | None = None) -> bool:
    today = today or business_today()
    return membership.state == Membership.State.ACTIVE and membership.next_due_date <= today + timedelta(days=7)


# --- Figures for the dashboards and reports (T23) -----------------------------------------------------------------


def status_counts(library, *, today: date | None = None) -> dict[str, int]:
    """Non-archived members by derived status: {active, due, overdue}. Same rules as the directory (#50)."""
    counts = {ACTIVE: 0, DUE: 0, OVERDUE: 0}
    for status in counts:
        counts[status] = owner_members(library, status=status).count()
    return counts


def upcoming_renewals(library, *, days: int = 7, today: date | None = None) -> QuerySet[Membership]:
    """Active members whose due date falls from today to `days` days ahead (dashboard `upcoming_renewals_7d`)."""
    today = today or business_today()
    return Membership.objects.filter(
        library=library,
        state=Membership.State.ACTIVE,
        next_due_date__gte=today,
        next_due_date__lte=today + timedelta(days=days),
    )


def new_memberships_on(library, day: date) -> int:
    """Memberships created on a business date: the dashboard's `new_bookings`."""
    return Membership.objects.filter(library=library, created_at__date=day).count()


def domain_breakdown(library) -> list[dict]:
    """Current (non-archived) members per exam domain, largest first; students without a domain are not counted."""
    from django.db.models import Count

    rows = (
        Membership.objects.filter(library=library, state=Membership.State.ACTIVE, student__domain__isnull=False)
        .values("student__domain__code", "student__domain__name")
        .annotate(count=Count("id"))
        .order_by("-count", "student__domain__name")
    )
    return [{"code": r["student__domain__code"], "name": r["student__domain__name"], "count": r["count"]} for r in rows]


def library_members_for_export(library, *, status: str | None = None) -> QuerySet[Membership]:
    queryset = _with_status(Membership.objects.filter(library=library)).order_by("student__name", "pk")
    return queryset.filter(status=status) if status in MEMBER_STATUSES else queryset
