from django.contrib import admin

from .models import Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    """Read-only staff support view: memberships change only through the product services."""

    list_display = ("student", "library", "plan", "source", "state", "start_date", "next_due_date")
    list_filter = ("state", "source")
    search_fields = ("student__email", "student__phone", "library__name")
    list_select_related = ("student", "library", "plan")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
