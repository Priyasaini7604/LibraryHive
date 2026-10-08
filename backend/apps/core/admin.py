from django.contrib import admin

from .models import Amenity, AuditLog, Domain


@admin.register(Domain, Amenity)
class VocabularyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "code")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: the audit trail is append-only (SECURITY.md section 15)."""

    list_display = ("created_at", "action", "entity_type", "entity_id", "actor", "actor_role")
    list_filter = ("action", "entity_type", "actor_role")
    search_fields = ("entity_id", "request_id", "action")
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
