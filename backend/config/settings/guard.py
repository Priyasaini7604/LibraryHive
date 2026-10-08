"""Production startup guard (SECURITY.md section 13).

`unsafe_settings_errors` is a pure function so it can be unit tested; the
production settings module raises ImproperlyConfigured if it returns errors.
"""

MIN_SECRET_LENGTH = 50


def unsafe_settings_errors(
    *,
    debug: bool,
    secret_key: str,
    jwt_signing_key: str,
    allowed_hosts: list[str],
    cors_allowed_origins: list[str],
    environment: str,
    razorpay_key_id: str = "",
) -> list[str]:
    errors: list[str] = []
    if debug:
        errors.append("DEBUG must be False.")
    if len(secret_key or "") < MIN_SECRET_LENGTH or secret_key.startswith("django-insecure"):
        errors.append(f"SECRET_KEY must be a random value of at least {MIN_SECRET_LENGTH} characters.")
    if len(jwt_signing_key or "") < MIN_SECRET_LENGTH:
        errors.append(f"JWT_SIGNING_KEY must be a random value of at least {MIN_SECRET_LENGTH} characters.")
    if jwt_signing_key and jwt_signing_key == secret_key:
        errors.append("JWT_SIGNING_KEY must differ from SECRET_KEY.")
    if not allowed_hosts or "*" in allowed_hosts:
        errors.append("ALLOWED_HOSTS must list explicit host names (no '*').")
    if not cors_allowed_origins or "*" in cors_allowed_origins:
        errors.append("CORS_ALLOWED_ORIGINS must list explicit origins (no '*').")
    if environment == "production" and razorpay_key_id.startswith("rzp_test_"):
        errors.append("Razorpay test keys must not be used when ENVIRONMENT=production.")
    return errors
