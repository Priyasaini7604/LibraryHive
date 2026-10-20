"""Read-side queries for libraries (BACKEND_ARCHITECTURE.md section 8).

Seat figures come from `seats.selectors` once that app exists (T10); until then
they are absent, never faked.
"""

import math
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.db.models import Min, Prefetch, Q, QuerySet

from .models import Library, LibraryPhoto, PricingPlan

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEGREE = 111.32


def _seat_selectors():
    return import_module("apps.seats.selectors") if apps.is_installed("apps.seats") else None


def active_seat_count(library: Library) -> int:
    seats = _seat_selectors()
    return seats.active_seat_count(library) if seats else 0


def _seat_counts_provider():
    """`seats.selectors.seat_counts_by_library`, once the derived seat status exists (T11 completion, T12)."""
    seats = _seat_selectors()
    return getattr(seats, "seat_counts_by_library", None) if seats else None


def seat_counts_by_library(library_ids: list) -> dict | None:
    """{library_id: {total, empty, reserved, occupied}}, or None while the seat status is not available yet."""
    provider = _seat_counts_provider()
    return provider(library_ids) if provider else None


def seat_counts_available() -> bool:
    return _seat_counts_provider() is not None


def domain_breakdown(library: Library) -> list[dict]:
    """[{code, name, count}] of current members per exam domain (#15). Counts only, never identities.

    Read through `memberships.selectors`, the same query as the owner dashboard (BACKEND_ARCHITECTURE section 3),
    so the public and owner figures cannot disagree. A library without members gets an empty list.
    """
    return import_module("apps.memberships.selectors").domain_breakdown(library)


def plan_in_use(plan: PricingPlan) -> bool:
    """True if any row (membership, payment, hold ...) references this plan.

    Walks the reverse relations, so each app that adds a plan foreign key is
    counted without this module importing it.
    """
    for rel in PricingPlan._meta.related_objects:
        if rel.related_model._default_manager.filter(**{rel.field.name: plan}).exists():
            return True
    return False


def publish_checklist(library: Library) -> dict[str, bool]:
    return {
        "has_profile": bool(library.name and library.address and library.city),
        "has_location": library.latitude is not None and library.longitude is not None,
        "has_active_plan": library.plans.filter(is_active=True).exists(),
        "has_active_seat": active_seat_count(library) > 0,
    }


def owner_photos(library: Library) -> QuerySet[LibraryPhoto]:
    return LibraryPhoto.objects.filter(library=library)


def owner_plans(library: Library) -> QuerySet[PricingPlan]:
    return PricingPlan.objects.filter(library=library)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lat = p2 - p1
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    d_lat = radius_km / KM_PER_DEGREE
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    d_lng = radius_km / (KM_PER_DEGREE * cos_lat)
    return lat - d_lat, lat + d_lat, lng - d_lng, lng + d_lng


def public_libraries(
    *,
    search: str | None = None,
    domain: str | None = None,
    amenities: list[str] | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float = 5,
    sort: str | None = None,
) -> list[Library]:
    """Published, active libraries with `starting_price` and, when a point is given, `distance_km`.

    A bounding box narrows the rows in SQL, then the exact distance decides.
    Domains and amenities are prefetched, so the query count does not grow
    with the number of libraries.
    """
    qs = (
        Library.objects.filter(is_published=True, is_active=True)
        .annotate(starting_price=Min("plans__price", filter=Q(plans__is_active=True)))
        .prefetch_related(
            "domains",
            "amenities",
            Prefetch("photos", queryset=LibraryPhoto.objects.filter(is_cover=True), to_attr="cover_photos"),
        )
    )
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(city__icontains=search) | Q(area__icontains=search))
    if domain:
        qs = qs.filter(domains__code=domain)
    for code in dict.fromkeys(amenities or []):
        qs = qs.filter(amenities__code=code)

    has_point = lat is not None and lng is not None
    if has_point:
        min_lat, max_lat, min_lng, max_lng = _bounding_box(lat, lng, radius_km)
        qs = qs.filter(latitude__gte=min_lat, latitude__lte=max_lat, longitude__gte=min_lng, longitude__lte=max_lng)

    libraries = list(qs.distinct())

    if has_point:
        nearby = []
        for library in libraries:
            distance = haversine_km(lat, lng, float(library.latitude), float(library.longitude))
            if distance <= radius_km:
                library.distance_km = round(distance, 2)
                nearby.append(library)
        libraries = nearby

    no_price = Decimal("Infinity")
    if sort == "distance":
        libraries.sort(key=lambda lib: (lib.distance_km, lib.name.lower()))
    elif sort == "price":
        libraries.sort(
            key=lambda lib: (no_price if lib.starting_price is None else lib.starting_price, lib.name.lower())
        )
    elif sort == "available":
        counts = seat_counts_by_library([lib.pk for lib in libraries]) or {}
        libraries.sort(key=lambda lib: (-counts.get(lib.pk, {}).get("empty", 0), lib.name.lower()))
    elif has_point:
        libraries.sort(key=lambda lib: (lib.distance_km, lib.name.lower()))
    else:
        libraries.sort(key=lambda lib: lib.name.lower())
    return libraries


def public_library(library_id) -> Library | None:
    return (
        Library.objects.filter(pk=library_id, is_published=True, is_active=True)
        .prefetch_related("domains", "amenities", "photos", "plans")
        .first()
    )
