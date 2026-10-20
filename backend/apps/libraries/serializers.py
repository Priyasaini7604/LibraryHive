"""Input validation and output shapes for libraries. No side effects here."""

from decimal import Decimal

from rest_framework import serializers

from apps.accounts.phone import InvalidPhone, normalize_phone
from apps.core.serializers import AmenitySerializer, DomainSerializer
from apps.core.storage import public_storage

from . import selectors
from .models import Library, LibraryPhoto, PricingPlan

SORT_CHOICES = ("distance", "price", "available")


def _quantize(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 6)))


class LibraryInput(serializers.Serializer):
    """Create (#17) and edit (#19, partial). Plans and seats have their own endpoints."""

    name = serializers.CharField(min_length=2, max_length=150, trim_whitespace=True)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    address = serializers.CharField(min_length=3, max_length=255, trim_whitespace=True)
    city = serializers.CharField(min_length=2, max_length=80, trim_whitespace=True)
    area = serializers.CharField(max_length=80, required=False, allow_blank=True)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False, allow_null=True)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False, allow_null=True)
    contact_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)
    contact_email = serializers.EmailField(max_length=254, required=False, allow_blank=True, allow_null=True)
    opens_at = serializers.TimeField(required=False, allow_null=True)
    closes_at = serializers.TimeField(required=False, allow_null=True)
    operating_notes = serializers.CharField(max_length=200, required=False, allow_blank=True)
    domain_codes = serializers.ListField(child=serializers.CharField(max_length=40), required=False, max_length=20)
    amenity_codes = serializers.ListField(child=serializers.CharField(max_length=40), required=False, max_length=30)

    def validate_contact_phone(self, value):
        if not value:
            return None
        try:
            return normalize_phone(value)
        except InvalidPhone as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_contact_email(self, value):
        return value.lower() if value else None

    def validate(self, attrs):
        for key in ("latitude", "longitude"):
            if key in attrs:
                attrs[key] = _quantize(attrs[key])
        return attrs


class PlanInput(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=60, trim_whitespace=True)
    duration_days = serializers.IntegerField(min_value=1, max_value=366)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    timing_note = serializers.CharField(max_length=100, required=False, allow_blank=True)


class PublicListQuery(serializers.Serializer):
    search = serializers.CharField(max_length=100, required=False, allow_blank=True)
    domain = serializers.CharField(max_length=40, required=False, allow_blank=True)
    amenity = serializers.ListField(child=serializers.CharField(max_length=40), required=False, max_length=30)
    lat = serializers.FloatField(min_value=-90, max_value=90, required=False)
    lng = serializers.FloatField(min_value=-180, max_value=180, required=False)
    radius_km = serializers.FloatField(min_value=0.1, max_value=50, required=False, default=5)
    sort = serializers.ChoiceField(choices=SORT_CHOICES, required=False)

    def validate(self, attrs):
        if ("lat" in attrs) != ("lng" in attrs):
            raise serializers.ValidationError({"lat": ["Send lat and lng together."]})
        if attrs.get("sort") == "distance" and "lat" not in attrs:
            raise serializers.ValidationError({"sort": ["Sorting by distance needs lat and lng."]})
        if attrs.get("sort") == "available" and not selectors.seat_counts_available():
            raise serializers.ValidationError({"sort": ["Sorting by availability is not available yet."]})
        return attrs


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingPlan
        fields = ["id", "name", "duration_days", "price", "timing_note"]
        read_only_fields = fields


class OwnerPlanSerializer(serializers.ModelSerializer):
    in_use = serializers.SerializerMethodField()

    class Meta:
        model = PricingPlan
        fields = ["id", "name", "duration_days", "price", "timing_note", "is_active", "in_use"]
        read_only_fields = fields

    def get_in_use(self, plan) -> bool:
        return selectors.plan_in_use(plan)


class PhotoInput(serializers.Serializer):
    caption = serializers.CharField(max_length=150, required=False, allow_blank=True)
    display_order = serializers.IntegerField(min_value=0, max_value=1000, required=False)


class PhotoUploadInput(serializers.Serializer):
    image = serializers.FileField()
    caption = serializers.CharField(max_length=150, required=False, allow_blank=True)


class PublicPhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    thumb_url = serializers.SerializerMethodField()

    class Meta:
        model = LibraryPhoto
        fields = ["id", "url", "thumb_url", "caption", "is_cover"]
        read_only_fields = fields

    def get_url(self, photo) -> str:
        return public_storage().url(photo.image)

    def get_thumb_url(self, photo) -> str:
        return public_storage().url(photo.thumbnail)


class OwnerPhotoSerializer(PublicPhotoSerializer):
    class Meta:
        model = LibraryPhoto
        fields = ["id", "url", "thumb_url", "caption", "display_order", "is_cover", "width", "height"]
        read_only_fields = fields


class _Coordinates(serializers.ModelSerializer):
    latitude = serializers.FloatField(read_only=True, allow_null=True)
    longitude = serializers.FloatField(read_only=True, allow_null=True)


class OwnerLibrarySerializer(_Coordinates):
    domains = DomainSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)
    publish_checklist = serializers.SerializerMethodField()

    class Meta:
        model = Library
        fields = [
            "id",
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
            "domains",
            "amenities",
            "is_published",
            "is_active",
            "publish_checklist",
        ]
        read_only_fields = fields

    def get_publish_checklist(self, library) -> dict:
        return selectors.publish_checklist(library)


class PublicLibraryDetailSerializer(_Coordinates):
    domains = DomainSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)
    plans = serializers.SerializerMethodField()
    photos = PublicPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Library
        fields = [
            "id",
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
            "amenities",
            "domains",
            "plans",
            "photos",
        ]
        read_only_fields = fields

    def get_plans(self, library) -> list:
        active = [plan for plan in library.plans.all() if plan.is_active]
        return PlanSerializer(active, many=True).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        counts = selectors.seat_counts_by_library([instance.pk])
        if counts is not None:
            data["seat_counts"] = counts.get(instance.pk, {"total": 0, "empty": 0, "reserved": 0, "occupied": 0})
        data["domain_breakdown"] = selectors.domain_breakdown(instance)
        return data


class PublicLibraryListSerializer(serializers.ModelSerializer):
    amenities = serializers.SerializerMethodField()
    domains = serializers.SerializerMethodField()
    starting_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)

    class Meta:
        model = Library
        fields = ["id", "name", "city", "area", "amenities", "domains", "starting_price"]
        read_only_fields = fields

    def get_amenities(self, library) -> list[str]:
        return sorted(a.code for a in library.amenities.all())

    def get_domains(self, library) -> list[str]:
        return sorted(d.code for d in library.domains.all())

    def to_representation(self, instance):
        data = super().to_representation(instance)
        cover = next(iter(getattr(instance, "cover_photos", [])), None)
        if cover is not None:
            data["cover"] = {"thumb_url": public_storage().url(cover.thumbnail)}
        if hasattr(instance, "distance_km"):
            data["distance_km"] = instance.distance_km
        counts = self.context.get("seat_counts")
        if counts is not None:
            data["seat_counts"] = counts.get(instance.pk, {"total": 0, "empty": 0, "reserved": 0, "occupied": 0})
        return data
