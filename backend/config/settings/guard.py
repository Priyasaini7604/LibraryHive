"""Production startup guard (SECURITY.md section 13).

`unsafe_settings_errors` is a pure function so it can be unit tested; the
production settings module raises ImproperlyConfigured if it returns errors.
"""

MIN_SECRET_LENGTH = 50

# Email backends that never leave the machine: console prints the message, the others keep or drop it.
# Marking a delivery `sent` through one of them would report an email that nobody received.
NON_DELIVERING_EMAIL_BACKENDS = frozenset(
    {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    }
)


def unsafe_settings_errors(
    *,
    debug: bool,
    secret_key: str,
    jwt_signing_key: str,
    allowed_hosts: list[str],
    cors_allowed_origins: list[str],
    environment: str,
    storage_backend: str,
    public_bucket: str,
    private_bucket: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    razorpay_key_id: str = "",
    email_notifications_enabled: bool = False,
    email_backend: str = "",
    aws_endpoint_url: str = "",
    aws_region_name: str = "",
    media_public_base_url: str = "",
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
    if environment == "production":
        # Hosts such as Render and Railway have an ephemeral disk: a file written there is gone at the next
        # deploy. QR codes, payment screenshots and library photos must live in object storage.
        if storage_backend != "s3":
            errors.append(
                "STORAGE_BACKEND must be 's3' in production: local files are lost at every deploy on an ephemeral disk."
            )
        else:
            missing = [
                name
                for name, value in (
                    ("AWS_STORAGE_BUCKET_NAME", public_bucket),
                    ("AWS_PRIVATE_BUCKET_NAME", private_bucket),
                    ("AWS_ACCESS_KEY_ID", aws_access_key_id),
                    ("AWS_SECRET_ACCESS_KEY", aws_secret_access_key),
                )
                if not (value or "").strip()
            ]
            if missing:
                errors.append(f"STORAGE_BACKEND=s3 needs {', '.join(missing)}.")
            elif public_bucket == private_bucket:
                errors.append(
                    "AWS_PRIVATE_BUCKET_NAME must be a different bucket from AWS_STORAGE_BUCKET_NAME: "
                    "payment screenshots and QR codes must never share the public bucket."
                )
            if (aws_endpoint_url or "").strip():
                # A custom endpoint means an S3-compatible provider (Supabase, R2, MinIO). Presigned links are
                # signed for one region, and botocore would otherwise guess us-east-1: the private links would
                # then fail with SignatureDoesNotMatch.
                if not (aws_region_name or "").strip():
                    errors.append(
                        "AWS_S3_REGION_NAME is required when AWS_S3_ENDPOINT_URL is set (for example ap-south-1)."
                    )
                if not aws_endpoint_url.strip().lower().startswith("https://"):
                    errors.append("AWS_S3_ENDPOINT_URL must start with https://.")
                # The provider's S3 endpoint needs credentials; public photos are served from another URL.
                base = (media_public_base_url or "").strip()
                if not base:
                    errors.append(
                        "MEDIA_PUBLIC_BASE_URL is required when AWS_S3_ENDPOINT_URL is set: "
                        "the full public URL prefix of the public bucket, including its path."
                    )
                elif not base.lower().startswith("https://"):
                    errors.append("MEDIA_PUBLIC_BASE_URL must start with https://.")
    if email_notifications_enabled and email_backend in NON_DELIVERING_EMAIL_BACKENDS:
        errors.append(
            "EMAIL_NOTIFICATIONS_ENABLED needs a real EMAIL_BACKEND; "
            "the console, locmem, dummy and file backends would mark emails as sent without delivering them."
        )
    return errors
