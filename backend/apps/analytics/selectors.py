"""Dashboard and report figures (BACKEND_ARCHITECTURE.md 9.12, #82-#89).

Every number comes from the owning app's selector, the same one its list endpoint uses, so a dashboard card
and the list it links to cannot disagree. Nothing here is stored or cached.
"""

from datetime import date

from django.db.models import QuerySet

from apps.attendance import selectors as attendance
from apps.complaints import selectors as complaints
from apps.core.dates import business_today
from apps.core.models import AuditLog
from apps.libraries import selectors as library_selectors
from apps.memberships import selectors as memberships
from apps.payments import selectors as payments
from apps.seats import selectors as seats
from apps.visits import selectors as visits
from apps.visits.models import VisitRequest

MAX_REVENUE_DAYS = 366


def owner_dashboard(library, *, today: date | None = None) -> dict:
    """The owner's KPI dashboard (#82)."""
    today = today or business_today()
    counts = seats.library_seat_counts(library)
    month = payments.revenue_between(library, today.replace(day=1), today)
    return {
        "seats": {
            "total": counts["total"],
            "empty": counts["empty"],
            "reserved": counts["reserved"],
            "occupied": counts["occupied"],
            "disabled": counts["total"] - counts["empty"] - counts["reserved"] - counts["occupied"],
        },
        "members": memberships.status_counts(library),
        "today": {
            "new_bookings": memberships.new_memberships_on(library, today),
            "check_ins": attendance.check_ins_today(library, today=today),
            "present_now": attendance.present_now_count(library),
        },
        "upcoming_renewals_7d": memberships.upcoming_renewals(library, days=7, today=today).count(),
        "revenue": {"this_month_total": month["total"], "by_method": month["by_method"]},
        "open_complaints": complaints.open_count(library),
        "pending_visits": visits.pending_count(library),
        "domain_breakdown": memberships.domain_breakdown(library),
        "publish_checklist": library_selectors.publish_checklist(library),
    }


def occupancy_report(library) -> dict:
    counts = seats.library_seat_counts(library)
    return {"counts": counts, "by_row": seats.seat_counts_by_row(library)}


def revenue_report(library, start: date, end: date) -> dict:
    return payments.revenue_between(library, start, end)


def complaint_report(library, *, date_from: date | None = None, date_to: date | None = None) -> dict:
    return {
        "by_status": complaints.counts_by(library, "status", date_from=date_from, date_to=date_to),
        "by_category": complaints.counts_by(library, "category", date_from=date_from, date_to=date_to),
    }


def domain_report(library) -> list[dict]:
    return memberships.domain_breakdown(library)


def audit_entries(
    library,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> QuerySet[AuditLog]:
    """The library's activity log, newest first (#88). Library-scoped; the IP address is never selected for display."""
    queryset = AuditLog.objects.filter(library=library).select_related("actor").order_by("-created_at")
    if action:
        queryset = queryset.filter(action=action)
    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def student_dashboard(student, *, today: date | None = None) -> dict:
    """The student's home (#89): their own data only."""
    today = today or business_today()
    current = memberships.student_memberships(student)
    hold = seats.current_booking_holds(student).first()
    upcoming_visits = (
        VisitRequest.objects.filter(student=student, preferred_date__gte=today)
        .filter(status__in=[VisitRequest.Status.PENDING, VisitRequest.Status.ACCEPTED])
        .select_related("library")
        .order_by("preferred_date")
    )
    return {
        "memberships": list(current),
        "current_attendance": attendance.current_record(student),
        "recent_payments": list(payments.student_payments(student)[:3]),
        "open_complaints": complaints.student_open_count(student),
        "visits": list(upcoming_visits[:5]),
        "pending_hold": hold,
    }
