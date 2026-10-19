from django.contrib import admin

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    """Staff support view. Status changes go through the complaint services (audited, student notified)."""

    list_display = ("category", "status", "library", "student", "created_at")
    list_filter = ("status", "category")
    list_select_related = ("library", "student")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
