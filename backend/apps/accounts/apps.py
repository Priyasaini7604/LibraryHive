from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        from apps.core.exceptions import register_constraint_error

        # Races that slip past the service checks still return a clean 409.
        register_constraint_error(
            "user_email_unique", code="EMAIL_TAKEN", message="An account with this email already exists."
        )
        register_constraint_error(
            "user_phone_unique", code="PHONE_TAKEN", message="An account with this phone number already exists."
        )
