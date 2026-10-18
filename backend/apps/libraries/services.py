"""All library and plan state changes (BACKEND_ARCHITECTURE.md section 8).

Views only parse, check permissions, call these and wrap the result.
"""

import logging
import uuid
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.core.images import process_upload
from apps.core.models import Amenity, Domain
from apps.core.storage import public_storage, save_bytes

from . import selectors
from .models import Library, LibraryPhoto, PricingPlan

logger = logging.getLogger("apps.libraries")

PROFILE_FIELDS = (
    "name",
    "description",
    "address",
    "city",
    "area",
    "latitude",
    "longitude",
    "contact_phone",
    "contact_email",
    "opens_at",
    "closes_at",
    "operating_notes",
)
PLAN_FIELDS = ("name", "duration_days", "price", "timing_note")
PLAN_NAME_TAKEN = "You already have an active plan with this name."


def _snapshot(library: Library) -> dict[str, Any]:
    data = {field: getattr(library, field) for field in PROFILE_FIELDS}
    data["domain_codes"] = sorted(library.domains.values_list("code", flat=True))
    data["amenity_codes"] = sorted(library.amenities.values_list("code", flat=True))
    return data


def _vocabulary(model, codes: list[str], field: str) -> list:
    wanted = list(dict.fromkeys(codes))
    found = {row.code: row for row in model.objects.filter(code__in=wanted, is_active=True)}
    missing = [code for code in wanted if code not in found]
    if missing:
        raise ValidationFailed(details={field: [f"Unknown value: {', '.join(missing)}."]})
    return [found[code] for code in wanted]


def _validate_coordinates(latitude, longitude) -> None:
    if (latitude is None) != (longitude is None):
        raise ValidationFailed(details={"latitude": ["Set latitude and longitude together or leave both empty."]})


def _locked(library: Library) -> Library:
    return Library.objects.select_for_update().get(pk=library.pk)


@transaction.atomic
def create_library(*, owner, data: dict[str, Any]) -> Library:
    """Onboarding step 1 (#17). One library per owner; starts unpublished."""
    if Library.objects.filter(owner=owner).exists():
        raise Conflict("You already have a library.", code="LIBRARY_EXISTS")
    data = dict(data)
    domains = _vocabulary(Domain, data.pop("domain_codes", []), "domain_codes")
    amenities = _vocabulary(Amenity, data.pop("amenity_codes", []), "amenity_codes")
    _validate_coordinates(data.get("latitude"), data.get("longitude"))
    try:
        with transaction.atomic():
            library = Library.objects.create(owner=owner, **{k: v for k, v in data.items() if k in PROFILE_FIELDS})
    except IntegrityError as exc:  # two creates raced on the one-to-one owner
        raise Conflict("You already have a library.", code="LIBRARY_EXISTS") from exc
    library.domains.set(domains)
    library.amenities.set(amenities)
    audit.record(
        actor=owner,
        action="library.create",
        entity_type="library",
        entity_id=library.pk,
        library=library,
        changes={"name": library.name},
    )
    logger.info("Library created", extra={"library_id": str(library.pk), "owner_id": str(owner.pk)})
    return refresh_publish_state(library)


@transaction.atomic
def update_library(*, library: Library, actor, data: dict[str, Any]) -> Library:
    """Edit the profile (#19); any subset of the create fields. Audited with a diff."""
    library = _locked(library)
    before = _snapshot(library)
    data = dict(data)
    if "domain_codes" in data:
        library.domains.set(_vocabulary(Domain, data.pop("domain_codes"), "domain_codes"))
    if "amenity_codes" in data:
        library.amenities.set(_vocabulary(Amenity, data.pop("amenity_codes"), "amenity_codes"))
    for field, value in data.items():
        if field in PROFILE_FIELDS:
            setattr(library, field, value)
    _validate_coordinates(library.latitude, library.longitude)
    if library.latitude is None:
        # The database refuses a published library without coordinates, so drop the flag in the same save.
        library.is_published = False
        library.published_at = None
    library.save()
    audit.record(
        actor=actor,
        action="library.update",
        entity_type="library",
        entity_id=library.pk,
        library=library,
        changes=audit.changes_between(before, _snapshot(library)),
    )
    return refresh_publish_state(library)


def refresh_publish_state(library: Library) -> Library:
    """published <=> active, profile and location set, >= 1 active plan, >= 1 active seat (LIB-07).

    Called after anything that feeds the rule changes. Safe to call repeatedly.
    """
    checklist = selectors.publish_checklist(library)
    should_publish = library.is_active and all(checklist.values())
    if should_publish != library.is_published:
        library.is_published = should_publish
        library.published_at = timezone.now() if should_publish else None
        library.save(update_fields=["is_published", "published_at", "updated_at"])
        logger.info(
            "Library publish state changed",
            extra={"library_id": str(library.pk), "is_published": should_publish},
        )
    return library


def _clean_plan(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in data.items() if k in PLAN_FIELDS}
    if "name" in cleaned:
        cleaned["name"] = cleaned["name"].strip()
    return cleaned


def _name_taken(library: Library, name: str, *, exclude: PricingPlan | None = None) -> bool:
    qs = PricingPlan.objects.filter(library=library, is_active=True, name__iexact=name)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.exists()


def _plan_snapshot(plan: PricingPlan) -> dict[str, Any]:
    return {**{f: getattr(plan, f) for f in PLAN_FIELDS}, "is_active": plan.is_active}


def _locked_plan(library: Library, plan: PricingPlan) -> tuple[Library, PricingPlan]:
    library = _locked(library)
    try:
        return library, PricingPlan.objects.select_for_update().get(pk=plan.pk, library=library)
    except PricingPlan.DoesNotExist as exc:
        raise NotFound() from exc


@transaction.atomic
def create_plan(*, library: Library, actor, data: dict[str, Any]) -> PricingPlan:
    library = _locked(library)
    cleaned = _clean_plan(data)
    if _name_taken(library, cleaned["name"]):
        raise Conflict(PLAN_NAME_TAKEN, code="PLAN_NAME_TAKEN")
    plan = PricingPlan.objects.create(library=library, **cleaned)
    audit.record(
        actor=actor,
        action="plan.create",
        entity_type="pricing_plan",
        entity_id=plan.pk,
        library=library,
        changes=audit.changes_between({}, _plan_snapshot(plan)),
    )
    refresh_publish_state(library)
    return plan


@transaction.atomic
def update_plan(*, library: Library, plan: PricingPlan, actor, data: dict[str, Any]) -> PricingPlan:
    """Edit a plan (#22). Affects future periods only: payments snapshot amounts."""
    library, plan = _locked_plan(library, plan)
    before = _plan_snapshot(plan)
    cleaned = _clean_plan(data)
    if plan.is_active and "name" in cleaned and _name_taken(library, cleaned["name"], exclude=plan):
        raise Conflict(PLAN_NAME_TAKEN, code="PLAN_NAME_TAKEN")
    for field, value in cleaned.items():
        setattr(plan, field, value)
    plan.save()
    audit.record(
        actor=actor,
        action="plan.update",
        entity_type="pricing_plan",
        entity_id=plan.pk,
        library=library,
        changes=audit.changes_between(before, _plan_snapshot(plan)),
    )
    return plan


@transaction.atomic
def deactivate_plan(*, library: Library, plan: PricingPlan, actor) -> PricingPlan:
    """Hide a plan from booking (#23). Existing memberships and payments keep it."""
    library, plan = _locked_plan(library, plan)
    if plan.is_active:
        plan.is_active = False
        plan.save(update_fields=["is_active", "updated_at"])
        audit.record(
            actor=actor, action="plan.deactivate", entity_type="pricing_plan", entity_id=plan.pk, library=library
        )
        refresh_publish_state(library)
    return plan


@transaction.atomic
def activate_plan(*, library: Library, plan: PricingPlan, actor) -> PricingPlan:
    """Re-enable a plan (#24); its name must still be unique among active plans."""
    library, plan = _locked_plan(library, plan)
    if not plan.is_active:
        if _name_taken(library, plan.name, exclude=plan):
            raise Conflict(PLAN_NAME_TAKEN, code="PLAN_NAME_TAKEN")
        plan.is_active = True
        plan.save(update_fields=["is_active", "updated_at"])
        audit.record(
            actor=actor, action="plan.activate", entity_type="pricing_plan", entity_id=plan.pk, library=library
        )
        refresh_publish_state(library)
    return plan


# --- Photos (T09, PHO-01..06) -------------------------------------------------------------


def _delete_objects(keys: list[str]) -> None:
    storage = public_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            logger.warning("Photo object delete failed", extra={"key": key})


def _locked_photo(library: Library, photo: LibraryPhoto) -> LibraryPhoto:
    try:
        return LibraryPhoto.objects.select_for_update().get(pk=photo.pk, library=library)
    except LibraryPhoto.DoesNotExist as exc:
        raise NotFound() from exc


def upload_photo(*, library: Library, actor, uploaded_file, caption: str = "") -> LibraryPhoto:
    """Verify, re-encode and store a photo (#26). At most MAX_LIBRARY_PHOTOS, counted under the Library lock.

    The first photo becomes the cover. Objects written before a failure are removed again.
    """
    processed = process_upload(uploaded_file)  # raises FILE_TYPE / FILE_TOO_LARGE before any state changes
    stored: list[str] = []
    try:
        with transaction.atomic():
            library = _locked(library)
            existing = LibraryPhoto.objects.filter(library=library)
            if existing.count() >= settings.MAX_LIBRARY_PHOTOS:
                raise Conflict(f"A library can have at most {settings.MAX_LIBRARY_PHOTOS} photos.", code="PHOTO_LIMIT")
            base = f"libraries/{library.pk}/{uuid.uuid4().hex}"
            storage = public_storage()
            image_key = save_bytes(storage, f"{base}.webp", processed.display)
            stored.append(image_key)
            thumb_key = save_bytes(storage, f"{base}_thumb.webp", processed.thumbnail)
            stored.append(thumb_key)
            last = existing.order_by("-display_order").values_list("display_order", flat=True).first()
            photo = LibraryPhoto.objects.create(
                library=library,
                image=image_key,
                thumbnail=thumb_key,
                width=processed.width,
                height=processed.height,
                size_bytes=processed.original_size,
                caption=caption.strip(),
                display_order=0 if last is None else last + 1,
                is_cover=last is None,
                uploaded_by=actor,
            )
            audit.record(
                actor=actor,
                action="photo.upload",
                entity_type="library_photo",
                entity_id=photo.pk,
                library=library,
                changes={"is_cover": photo.is_cover},
            )
    except Exception:
        _delete_objects(stored)
        raise
    return photo


@transaction.atomic
def update_photo(*, library: Library, photo: LibraryPhoto, actor, data: dict[str, Any]) -> LibraryPhoto:
    """Caption and order (#27)."""
    photo = _locked_photo(library, photo)
    before = {"caption": photo.caption, "display_order": photo.display_order}
    if "caption" in data:
        photo.caption = data["caption"].strip()
    if "display_order" in data:
        photo.display_order = data["display_order"]
    photo.save()
    audit.record(
        actor=actor,
        action="photo.update",
        entity_type="library_photo",
        entity_id=photo.pk,
        library=library,
        changes=audit.changes_between(before, {"caption": photo.caption, "display_order": photo.display_order}),
    )
    return photo


@transaction.atomic
def set_cover(*, library: Library, photo: LibraryPhoto, actor) -> LibraryPhoto:
    """Choose the cover (#28). The old cover is cleared first so the one-cover unique holds."""
    library = _locked(library)
    photo = _locked_photo(library, photo)
    if not photo.is_cover:
        LibraryPhoto.objects.filter(library=library, is_cover=True).update(is_cover=False)
        photo.is_cover = True
        photo.save(update_fields=["is_cover", "updated_at"])
        audit.record(
            actor=actor, action="photo.set_cover", entity_type="library_photo", entity_id=photo.pk, library=library
        )
    return photo


@transaction.atomic
def delete_photo(*, library: Library, photo: LibraryPhoto, actor) -> None:
    """Delete a photo (#29). A deleted cover passes to the lowest display_order photo; objects go after commit."""
    library = _locked(library)
    photo = _locked_photo(library, photo)
    keys = [photo.image, photo.thumbnail]
    was_cover = photo.is_cover
    photo_id = photo.pk
    photo.delete()
    if was_cover:
        successor = LibraryPhoto.objects.filter(library=library).order_by("display_order", "created_at").first()
        if successor is not None:
            successor.is_cover = True
            successor.save(update_fields=["is_cover", "updated_at"])
    audit.record(
        actor=actor,
        action="photo.delete",
        entity_type="library_photo",
        entity_id=photo_id,
        library=library,
        changes={"was_cover": was_cover},
    )
    transaction.on_commit(lambda: _delete_objects(keys))
