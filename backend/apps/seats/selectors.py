"""Read-side queries for seats (BACKEND_ARCHITECTURE.md section 8).

The seat status is derived, never stored (SPEC.md 4.1): disabled, then occupied
(`memberships`), then reserved (a live `SeatHold`), else empty.
"""

from django.db.models import Case, CharField, Count, Exists, OuterRef, QuerySet, Value, When

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


# --- Derived seat status (SPEC.md 4.1) ---------------------------------------------------------

EMPTY, RESERVED, OCCUPIED, DISABLED = "empty", "reserved", "occupied", "disabled"


def _memberships():
    """`memberships.selectors`, imported lazily so `seats` never imports memberships models at load time."""
    from apps.memberships import selectors

    return selectors


def _status_expression():
    """disabled, then occupied (active membership), then reserved (live hold), else empty: one SQL CASE."""
    return Case(
        When(is_disabled=True, then=Value(DISABLED)),
        When(_memberships().occupied_expression(), then=Value(OCCUPIED)),
        When(Exists(SeatHold.objects.live().filter(seat=OuterRef("pk"))), then=Value(RESERVED)),
        default=Value(EMPTY),
        output_field=CharField(),
    )


def _zero_counts() -> dict[str, int]:
    return {"total": 0, EMPTY: 0, RESERVED: 0, OCCUPIED: 0}


def seat_counts_by_library(library_ids) -> dict:
    """{library_id: {total, empty, reserved, occupied}} for the active seats, in one query (SEAT-08).

    `total` counts every active seat, disabled ones included, so a disabled seat is in `total` but in no
    other figure. Expired holds count as empty without any cleanup, because the live-hold rule decides.
    Every requested library is present, with zeros when it has no seats.
    """
    ids = list(library_ids)
    counts = {library_id: _zero_counts() for library_id in ids}
    rows = (
        Seat.objects.filter(library_id__in=ids, is_active=True)
        .annotate(status=_status_expression())
        .values("library_id", "status")
        .annotate(n=Count("id"))
    )
    for row in rows:
        figures = counts[row["library_id"]]
        figures["total"] += row["n"]
        if row["status"] != DISABLED:
            figures[row["status"]] += row["n"]
    return counts


def library_seat_counts(library) -> dict[str, int]:
    return seat_counts_by_library([library.pk])[library.pk]


def seat_map(library, *, include_inactive: bool = False) -> QuerySet[Seat]:
    """The library's seats in layout order with their derived `status` (None for removed seats)."""
    queryset = library_seats(library, include_inactive=include_inactive).annotate(
        status=Case(
            When(is_active=False, then=Value(None)),
            default=_status_expression(),
            output_field=CharField(null=True),
        )
    )
    return queryset


def owner_seat_map(library, *, include_inactive: bool = False, seat_ids=None) -> list[Seat]:
    """`seat_map` plus the owner-only detail: who occupies a seat and who holds it (#30).

    Detail is read for the owner's own seats only, in two extra queries however many seats there are.
    """
    queryset = seat_map(library, include_inactive=include_inactive)
    if seat_ids is not None:
        queryset = queryset.filter(pk__in=list(seat_ids))
    seats = list(queryset)
    ids = [seat.pk for seat in seats]
    occupants = _memberships().active_occupants(ids)
    holds = {hold.seat_id: hold for hold in SeatHold.objects.live().filter(seat_id__in=ids).select_related("student")}
    for seat in seats:
        seat.occupant = occupants.get(seat.pk)
        seat.live_hold = holds.get(seat.pk)
    return seats
