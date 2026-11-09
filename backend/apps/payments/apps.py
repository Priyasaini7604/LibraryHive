from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    label = "payments"

    def ready(self):
        from apps.core.exceptions import register_constraint_error

        register_constraint_error(
            "upireq_utr_unique_live",
            code="DUPLICATE_UTR",
            message="This UTR has already been submitted. Check the number, or contact the library.",
        )
        register_constraint_error(
            "upireq_one_pending_per_student",
            code="UPI_REQUEST_PENDING",
            message="You already have a payment request waiting for this library. Cancel it first to send a new one.",
        )
