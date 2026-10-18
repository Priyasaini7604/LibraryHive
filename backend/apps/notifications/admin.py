from django.contrib import admin

from .models import Notification, NotificationDelivery


class _ReadOnly(admin.ModelAdmin):
    """Staff support view of the delivery log (LOG-09). Notifications are created only by the product services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(_ReadOnly):
    list_display = ("type", "recipient", "title", "created_at", "read_at")
    list_filter = ("type",)
    search_fields = ("recipient__email", "dedup_key")


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(_ReadOnly):
    list_display = ("notification", "channel", "status", "attempts", "next_attempt_at", "sent_at")
    list_filter = ("status", "channel")
