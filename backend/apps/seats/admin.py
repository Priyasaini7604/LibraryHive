from django.contrib import admin

from .models import Seat


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    """Read-only staff support view: seats change only through the owner's seat manager."""

    list_display = ("label", "library", "row_label", "position", "is_active", "is_disabled")
    list_filter = ("is_active", "is_disabled")
    search_fields = ("label", "library__name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
