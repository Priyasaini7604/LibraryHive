from django.contrib import admin

from .models import VisitRequest


@admin.register(VisitRequest)
class VisitRequestAdmin(admin.ModelAdmin):
    """Staff support view. Decisions go through the visit services (audited, student notified)."""

    list_display = ("library", "student", "preferred_date", "preferred_slot", "status")
    list_filter = ("status", "preferred_slot")
    list_select_related = ("library", "student")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
