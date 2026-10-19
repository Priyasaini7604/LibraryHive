from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import BaseModel


class Library(BaseModel):
    """A study library run by one owner (SPEC.md 3.5).

    Never deleted: `is_active=False` hides it from discovery and blocks new
    bookings. `is_published` is maintained only by
    `libraries.services.refresh_publish_state()`.
    """

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="library")
    name = models.CharField(max_length=150)
    description = models.TextField(max_length=2000, blank=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    area = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    contact_phone = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001
    contact_email = models.EmailField(max_length=254, null=True, blank=True)  # noqa: DJ001
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    operating_notes = models.CharField(max_length=200, blank=True)
    domains = models.ManyToManyField("core.Domain", blank=True, related_name="libraries")
    amenities = models.ManyToManyField("core.Amenity", blank=True, related_name="libraries")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "libraries"
        indexes = [
            models.Index(fields=["is_published", "is_active"], name="library_published_active_idx"),
            models.Index(fields=["latitude", "longitude"], name="library_coords_idx"),
            models.Index(fields=["city"], name="library_city_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__isnull=True) | (Q(latitude__gte=-90) & Q(latitude__lte=90)),
                name="library_latitude_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__isnull=True) | (Q(longitude__gte=-180) & Q(longitude__lte=180)),
                name="library_longitude_range",
            ),
            models.CheckConstraint(
                condition=Q(latitude__isnull=True, longitude__isnull=True)
                | Q(latitude__isnull=False, longitude__isnull=False),
                name="library_coords_pair",
            ),
            models.CheckConstraint(
                condition=Q(is_published=False) | Q(latitude__isnull=False),
                name="library_published_requires_coords",
            ),
        ]

    def __str__(self):
        return self.name


class PricingPlan(BaseModel):
    """A purchasable membership period of a library (SPEC.md 3.7, decision D1).

    Seats are sold full-day: `timing_note` is descriptive only. Plans referenced
    by memberships or payments are deactivated, never deleted (PROTECT).
    """

    library = models.ForeignKey(Library, on_delete=models.PROTECT, related_name="plans")
    name = models.CharField(max_length=60)
    duration_days = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    timing_note = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price", "name"]
        indexes = [models.Index(fields=["library", "is_active"], name="pricingplan_library_active_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_days__gte=1) & Q(duration_days__lte=366),
                name="pricingplan_duration_range",
            ),
            models.CheckConstraint(condition=Q(price__gt=0), name="pricingplan_price_positive"),
            models.UniqueConstraint(
                "library",
                Lower("name"),
                condition=Q(is_active=True),
                name="pricingplan_unique_active_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.library_id})"


class LibraryPhoto(BaseModel):
    """A gallery photo (SPEC.md 3.6). The database stores keys and metadata only.

    Binaries live in the public object store under
    `libraries/{library_id}/{uuid}.webp` and `..._thumb.webp`.
    """

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="photos")
    image = models.CharField(max_length=255)
    thumbnail = models.CharField(max_length=255)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    size_bytes = models.PositiveIntegerField()
    caption = models.CharField(max_length=150, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_cover = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        ordering = ["display_order", "created_at"]
        indexes = [models.Index(fields=["library", "display_order"], name="libraryphoto_order_idx")]
        constraints = [
            models.UniqueConstraint(fields=["library"], condition=Q(is_cover=True), name="libraryphoto_one_cover"),
            models.CheckConstraint(condition=Q(size_bytes__lte=5242880), name="libraryphoto_size_limit"),
        ]

    def __str__(self):
        return f"photo {self.pk} of {self.library_id}"
