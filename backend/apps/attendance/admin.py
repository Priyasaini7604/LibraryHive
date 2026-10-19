from django.contrib import admin

from .models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Staff support view. Records change only through the attendance services (they are audited)."""

    list_display = ("student", "library", "date", "check_in_at", "check_out_at", "status")
    list_filter = ("status", "check_in_method")
    list_select_related = ("student", "library")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
