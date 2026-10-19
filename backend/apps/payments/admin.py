from django.contrib import admin

from .models import Payment, PaymentWebhookEvent


class _ReadOnly(admin.ModelAdmin):
    """Staff support view of the money ledger. Payments change only through the payment services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(_ReadOnly):
    list_display = ("receipt_number", "student", "library", "amount", "status", "channel", "method", "created_at")
    list_filter = ("status", "channel", "method")
    search_fields = ("receipt_number", "gateway_order_id", "student__email")
    list_select_related = ("student", "library")


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(_ReadOnly):
    list_display = ("event_id", "event_type", "result", "received_at")
    list_filter = ("result", "event_type")
