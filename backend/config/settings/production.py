"""Production and staging settings (ENVIRONMENT=production or staging)."""

from decouple import config
from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import (
    ALLOWED_HOSTS,
    AWS_ACCESS_KEY_ID,
    AWS_PRIVATE_BUCKET_NAME,
    AWS_SECRET_ACCESS_KEY,
    AWS_STORAGE_BUCKET_NAME,
    CORS_ALLOWED_ORIGINS,
    EMAIL_BACKEND,
    ENVIRONMENT,
    MIDDLEWARE,
    SECRET_KEY,
    SIMPLE_JWT,
    STORAGE_BACKEND,
    STORAGES,
)
from .guard import unsafe_settings_errors

DEBUG = False
SCHEMA_PUBLIC = False

# Email stays off until a real provider is configured: with the default console backend a delivery would be
# marked `sent` although nobody received it. Turn it on with EMAIL_NOTIFICATIONS_ENABLED=true plus a real
# EMAIL_BACKEND; the guard below refuses the combination with a backend that does not deliver.
EMAIL_NOTIFICATIONS_ENABLED = config("EMAIL_NOTIFICATIONS_ENABLED", default=False, cast=bool)

_errors = unsafe_settings_errors(
    debug=config("DEBUG", default=False, cast=bool),
    secret_key=SECRET_KEY,
    jwt_signing_key=SIMPLE_JWT["SIGNING_KEY"],
    allowed_hosts=list(ALLOWED_HOSTS),
    cors_allowed_origins=list(CORS_ALLOWED_ORIGINS),
    environment=ENVIRONMENT,
    storage_backend=STORAGE_BACKEND,
    public_bucket=AWS_STORAGE_BUCKET_NAME,
    private_bucket=AWS_PRIVATE_BUCKET_NAME,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    razorpay_key_id=config("RAZORPAY_KEY_ID", default=""),
    email_notifications_enabled=EMAIL_NOTIFICATIONS_ENABLED,
    email_backend=EMAIL_BACKEND,
)
if _errors:
    raise ImproperlyConfigured("Unsafe production settings: " + " ".join(_errors))

# HTTPS behind the platform proxy (SECURITY.md section 11).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
# The platform health probe (Railway, Render) calls the container over plain http with no forwarded protocol header,
# so it would be redirected and judged unhealthy. Only the health path is exempt; it reveals no data.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)  # enable after HTTPS is verified
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# WhiteNoise serves collected static files (Django admin) right after SecurityMiddleware.
MIDDLEWARE = [*MIDDLEWARE]
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1, "whitenoise.middleware.WhiteNoiseMiddleware"
)
