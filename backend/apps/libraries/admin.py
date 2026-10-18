from django.contrib import admin

from .models import Library, PricingPlan


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    """Staff support view. Owners manage libraries through the product, not here."""

    list_display = ("name", "city", "owner", "is_published", "is_active", "created_at")
    list_filter = ("is_published", "is_active", "city")
    search_fields = ("name", "city", "area", "owner__email")
    readonly_fields = ("is_published", "published_at")


@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "library", "duration_days", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "library__name")
