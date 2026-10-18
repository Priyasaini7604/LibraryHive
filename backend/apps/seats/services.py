"""All seat state changes (BACKEND_ARCHITECTURE.md section 8, SPEC.md 3.8).

Views only parse, check permissions, call these and wrap the result.
Removing (#33) and disabling (#34) a seat are not here yet: both must refuse a
seat with an active membership or a live hold, which needs
`memberships.selectors.active_membership_exists` (T11 completion) and the hold
model (T12). They are added with those, never as an unguarded shortcut.
"""

import logging
from dataclasses import dataclass

from django.db import transaction

from apps.core import audit
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.libraries import services as library_services
from apps.libraries.models import Library

from .models import Seat

logger = logging.getLogger("apps.seats")

MAX_SEATS_PER_REQUEST = 500


@dataclass(frozen=True)
class SeatSpec:
    label: str
    row_label: str = ""
    position: int | None = None


def grid_specs(rows: list[str], seats_per_row: int) -> list[SeatSpec]:
    """Labels "{row}-{n}" (A-1, A-2 ...) with `row_label` and `position` set (#31 grid mode)."""
    return [
        SeatSpec(label=f"{row}-{n}", row_label=row, position=n) for row in rows for n in range(1, seats_per_row + 1)
    ]


def _locked_library(library: Library) -> Library:
    return Library.objects.select_for_update().get(pk=library.pk)


def _locked_seat(library: Library, seat: Seat) -> Seat:
    try:
        return Seat.objects.select_for_update().get(pk=seat.pk, library=library)
    except Seat.DoesNotExist as exc:
        raise NotFound() from exc


@transaction.atomic
def create_seats(*, library: Library, actor, specs: list[SeatSpec]) -> tuple[list[Seat], list[dict]]:
    """Add seats (#31). Existing active labels are skipped, never reset or duplicated.

    The Library row is locked, so two requests adding the same labels cannot both create them.
    Returns (created, skipped).
    """
    if not specs:
        raise ValidationFailed(details={"seats": ["Add at least one seat."]})
    if len(specs) > MAX_SEATS_PER_REQUEST:
        raise ValidationFailed(details={"seats": [f"Add at most {MAX_SEATS_PER_REQUEST} seats per request."]})
    library = _locked_library(library)

    taken = {
        label.lower() for label in Seat.objects.filter(library=library, is_active=True).values_list("label", flat=True)
    }
    to_create: list[Seat] = []
    skipped: list[dict] = []
    for spec in specs:
        label = spec.label.strip()
        if label.lower() in taken:
            skipped.append({"label": label, "reason": "exists"})
            continue
        taken.add(label.lower())
        to_create.append(Seat(library=library, label=label, row_label=spec.row_label.strip(), position=spec.position))
    created = Seat.objects.bulk_create(to_create)

    audit.record(
        actor=actor,
        action="seat.create",
        entity_type="library",
        entity_id=library.pk,
        library=library,
        changes={"created": len(created), "skipped": len(skipped)},
    )
    library_services.refresh_publish_state(library)
    logger.info("Seats added", extra={"library_id": str(library.pk), "created": len(created), "skipped": len(skipped)})
    return created, skipped


@transaction.atomic
def update_seat(*, library: Library, seat: Seat, actor, data: dict) -> Seat:
    """Relabel or reposition a seat (#32). The label stays unique among active seats."""
    seat = _locked_seat(library, seat)
    before = {"label": seat.label, "row_label": seat.row_label, "position": seat.position}
    if "label" in data:
        label = data["label"].strip()
        clash = Seat.objects.filter(library=library, is_active=True, label__iexact=label).exclude(pk=seat.pk)
        if seat.is_active and clash.exists():
            raise Conflict("A seat with this label already exists in your library.")
        seat.label = label
    if "row_label" in data:
        seat.row_label = data["row_label"].strip()
    if "position" in data:
        seat.position = data["position"]
    seat.save()
    audit.record(
        actor=actor,
        action="seat.update",
        entity_type="seat",
        entity_id=seat.pk,
        library=library,
        changes=audit.changes_between(
            before, {"label": seat.label, "row_label": seat.row_label, "position": seat.position}
        ),
    )
    return seat


@transaction.atomic
def enable_seat(*, library: Library, seat: Seat, actor) -> Seat:
    """End maintenance on a seat (#35). Idempotent."""
    seat = _locked_seat(library, seat)
    if seat.is_disabled:
        seat.is_disabled = False
        seat.disabled_reason = ""
        seat.save(update_fields=["is_disabled", "disabled_reason", "updated_at"])
        audit.record(actor=actor, action="seat.enable", entity_type="seat", entity_id=seat.pk, library=library)
    return seat
