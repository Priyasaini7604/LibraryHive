"""Production and staging settings (ENVIRONMENT=production or staging)."""

from decouple import config
from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    ENVIRONMENT,
    MIDDLEWARE,
    SECRET_KEY,
    SIMPLE_JWT,
    STORAGES,
)
from .guard import unsafe_settings_errors

DEBUG = False
SCHEMA_PUBLIC = False

_errors = unsafe_settings_errors(
    debug=config("DEBUG", default=False, cast=bool),
    secret_key=SECRET_KEY,
    jwt_signing_key=SIMPLE_JWT["SIGNING_KEY"],
    allowed_hosts=list(ALLOWED_HOSTS),
    cors_allowed_origins=list(CORS_ALLOWED_ORIGINS),
    environment=ENVIRONMENT,
    razorpay_key_id=config("RAZORPAY_KEY_ID", default=""),
)
if _errors:
    raise ImproperlyConfigured("Unsafe production settings: " + " ".join(_errors))

# HTTPS behind the platform proxy (SECURITY.md section 11).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
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
