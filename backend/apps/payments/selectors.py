"""Read-side queries for payments (BACKEND_ARCHITECTURE.md section 8)."""

from datetime import date

from django.db.models import Q, QuerySet
from django.db.models.functions import Coalesce

from apps.core.search import phone_digits

from .models import Payment


def student_payments(student, *, order_id: str | None = None) -> QuerySet[Payment]:
    """The student's own payments, newest first (#44); `order_id` is an exact match used by checkout."""
    queryset = Payment.objects.filter(student=student).select_related("library")
    return queryset.filter(gateway_order_id=order_id) if order_id else queryset


def student_payment(student, payment_id) -> Payment | None:
    """One of the student's own payments with what the receipt shows (#45), or None."""
    return (
        Payment.objects.filter(pk=payment_id, student=student)
        .select_related("library", "plan", "membership__seat", "hold__seat")
        .first()
    )


def owner_payments(
    library,
    *,
    status: str | None = None,
    method: str | None = None,
    channel: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
) -> QuerySet[Payment]:
    """The library's payment ledger (#46), filterable. Dates apply to when the payment was paid, else created."""
    queryset = (
        Payment.objects.filter(library=library)
        .select_related("student", "recorded_by", "library", "plan")
        .annotate(event_at=Coalesce("paid_at", "created_at"))
    )
    if status:
        queryset = queryset.filter(status=status)
    if method:
        queryset = queryset.filter(method=method)
    if channel:
        queryset = queryset.filter(channel=channel)
    if date_from:
        queryset = queryset.filter(event_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(event_at__date__lte=date_to)
    if search:
        digits = phone_digits(search)
        match = Q(student__name__icontains=search)
        if digits:
            match |= Q(student__phone__contains=digits)
        queryset = queryset.filter(match)
    return queryset


def owner_payment(library, payment_id) -> Payment | None:
    return (
        Payment.objects.filter(pk=payment_id, library=library)
        .select_related("student", "recorded_by", "library", "plan", "membership__seat", "hold__seat")
        .first()
    )


def membership_payments(membership) -> QuerySet[Payment]:
    """The membership's successful payments, newest period first: its period history (SPEC.md 4.4)."""
    return (
        Payment.objects.filter(membership=membership, status=Payment.Status.SUCCESS)
        .select_related("plan")
        .order_by("-period_start", "-created_at")
    )


def revenue_between(library, start: date, end: date) -> dict:
    """Successful payments paid between two business dates, inclusive (#84). Only `success` counts as revenue."""
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth

    queryset = Payment.objects.filter(
        library=library, status=Payment.Status.SUCCESS, paid_at__date__gte=start, paid_at__date__lte=end
    )

    def grouped(field):
        return {
            row[field]: {"total": str(row["total"]), "count": row["count"]}
            for row in queryset.values(field).annotate(total=Sum("amount"), count=Count("id"))
        }

    months = (
        queryset.annotate(month=TruncMonth("paid_at"))
        .values("month")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("month")
    )
    totals = queryset.aggregate(total=Sum("amount"), count=Count("id"))
    return {
        "total": str(totals["total"] or 0),
        "count": totals["count"],
        "by_method": grouped("method"),
        "by_purpose": grouped("purpose"),
        "by_month": [
            {"month": row["month"].strftime("%Y-%m"), "total": str(row["total"]), "count": row["count"]}
            for row in months
        ],
    }


def library_payments_between(library, start: date | None = None, end: date | None = None) -> QuerySet[Payment]:
    """Every payment row of the library, optionally between two dates (CSV export)."""
    queryset = (
        Payment.objects.filter(library=library)
        .select_related("student", "plan")
        .annotate(event_at=Coalesce("paid_at", "created_at"))
        .order_by("-event_at")
    )
    if start:
        queryset = queryset.filter(event_at__date__gte=start)
    if end:
        queryset = queryset.filter(event_at__date__lte=end)
    return queryset
