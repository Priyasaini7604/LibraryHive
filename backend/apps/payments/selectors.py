"""Read-side queries for payments (BACKEND_ARCHITECTURE.md section 8)."""

from datetime import date

from django.db.models import Q, QuerySet
from django.db.models.functions import Coalesce

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
        digits = "".join(ch for ch in search if ch.isdigit())
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
