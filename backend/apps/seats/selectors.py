"""Read-side queries for seats (BACKEND_ARCHITECTURE.md section 8).

The derived seat status (SPEC.md 4.1) and `seat_counts_by_library` need
`memberships.selectors.active_membership_exists` and the live-hold rule, so they
arrive with the membership completion of T11 and with T12. Until then no status
is exposed, and nothing here invents one.
"""

from django.db.models import QuerySet

from .models import Seat, SeatHold


def library_seats(library, *, include_inactive: bool = False) -> QuerySet[Seat]:
    queryset = Seat.objects.filter(library=library)
    return queryset if include_inactive else queryset.filter(is_active=True)


def active_seat_count(library) -> int:
    """Seats that count towards the publish rule (LIB-07) and the seat total."""
    return Seat.objects.filter(library=library, is_active=True).count()


def live_hold_exists(seat) -> bool:
    """True if a live hold (SPEC.md 3.9) blocks the seat: booking hold not yet expired, or a manual hold."""
    return SeatHold.objects.live().filter(seat=seat).exists()


def current_booking_holds(student) -> QuerySet[SeatHold]:
    """The student's live booking holds with everything the checkout countdown shows (#39)."""
    return (
        SeatHold.objects.live()
        .filter(student=student, kind=SeatHold.Kind.BOOKING)
        .select_related("seat", "library", "plan")
        .order_by("expires_at")
    )
