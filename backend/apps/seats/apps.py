from django.apps import AppConfig


class SeatsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.seats"
    label = "seats"

    def ready(self):
        from apps.core.exceptions import register_constraint_error

        # A race that slips past the service checks still returns a clean 409.
        register_constraint_error(
            "seat_unique_active_label",
            code="CONFLICT",
            message="A seat with this label already exists in your library.",
        )
