from django.apps import AppConfig


class MembershipsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.memberships"
    label = "memberships"

    def ready(self):
        from apps.core.exceptions import register_constraint_error

        # A race that slips past the service checks still returns a clean 409.
        register_constraint_error(
            "membership_one_live_per_student_library",
            code="ALREADY_MEMBER",
            message="You already have a seat at this library.",
        )
