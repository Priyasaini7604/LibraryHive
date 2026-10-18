from django.apps import AppConfig


class LibrariesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.libraries"
    label = "libraries"

    def ready(self):
        from apps.core.exceptions import register_constraint_error

        # Races that slip past the service checks still return a clean 409.
        register_constraint_error(
            "pricingplan_unique_active_name",
            code="PLAN_NAME_TAKEN",
            message="You already have an active plan with this name.",
        )
