"""Read-side queries for direct UPI payments (SPEC.md 3.11b-c)."""

from datetime import timedelta

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.libraries.models import Library
from apps.memberships.models import Membership
from apps.seats.models import SeatHold

from .models import LibraryPaymentSettings, UpiPaymentRequest

_RELATED = ("library", "plan", "seat", "student", "reviewed_by", "payment")


def settings_for(library) -> LibraryPaymentSettings | None:
    return LibraryPaymentSettings.objects.filter(library=library).first()


def student_requests(student) -> QuerySet[UpiPaymentRequest]:
    return UpiPaymentRequest.objects.filter(student=student).select_related(*_RELATED)


def student_request(student, request_id) -> UpiPaymentRequest | None:
    return student_requests(student).filter(pk=request_id).first()


def owner_requests(library, *, status: str | None = None) -> QuerySet[UpiPaymentRequest]:
    queryset = UpiPaymentRequest.objects.filter(library=library).select_related(*_RELATED)
    return queryset.filter(status=status) if status else queryset


def owner_request(library, request_id) -> UpiPaymentRequest | None:
    return owner_requests(library).filter(pk=request_id).first()


def pending_summary(library) -> dict:
    """How many requests wait for the owner, and how many of those are past the review target."""
    pending = UpiPaymentRequest.objects.filter(library=library, status=UpiPaymentRequest.Status.PENDING)
    cutoff = timezone.now() - timedelta(hours=settings.UPI_REVIEW_TARGET_HOURS)
    return {"pending": pending.count(), "overdue": pending.filter(created_at__lte=cutoff).count()}


def payment_info_for_student(student, library_id) -> tuple[Library, LibraryPaymentSettings] | None:
    """The library's payment details, only for a student who is paying it right now.

    That means a live booking hold at this library or an active membership there (a renewal). Anyone else, and
    any other library, gets None (a 404), so a QR code is never handed to someone who is just browsing.
    """
    library = Library.objects.select_related("owner").filter(pk=library_id, is_active=True).first()
    if library is None:
        return None
    paying = (
        SeatHold.objects.live(timezone.now())
        .filter(student=student, library=library, kind=SeatHold.Kind.BOOKING)
        .exists()
        or Membership.objects.filter(student=student, library=library, state=Membership.State.ACTIVE).exists()
    )
    if not paying:
        return None
    row = settings_for(library)
    return (library, row) if row is not None and row.upi_enabled else None
