"""Settings shared by every environment.

All environment-specific and secret values come from environment variables
(read from backend/.env in development). See BACKEND_ARCHITECTURE.md section 13
and SECURITY.md section 13.
"""

from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

ENVIRONMENT = config("ENVIRONMENT", default="local")
APP_VERSION = config("APP_VERSION", default="dev")

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "storages",
    "apps.core",
    "apps.accounts",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.AccessLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database: PostgreSQL in every environment (AGENTS.md 2.2) ---------------
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL"),
        conn_max_age=config("DB_CONN_MAX_AGE", default=60, cast=int),
    )
}
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ValueError("DATABASE_URL must point to PostgreSQL (SQLite is not supported).")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache: database cache backs DRF throttling (no Redis, ARCHITECTURE 8.3) --
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "core_cache",
    }
}

# --- Passwords (SECURITY.md section 3) ---------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation: business dates are Asia/Kolkata (SPEC.md section 1)
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# --- Static and media ----------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / config("MEDIA_ROOT", default="media")

STORAGE_BACKEND = config("STORAGE_BACKEND", default="local")
if STORAGE_BACKEND not in {"local", "s3"}:
    raise ValueError("STORAGE_BACKEND must be 'local' or 's3'.")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_PRIVATE_BUCKET_NAME = config("AWS_PRIVATE_BUCKET_NAME", default="")
AWS_S3_ENDPOINT_URL = config("AWS_S3_ENDPOINT_URL", default="") or None
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
MEDIA_PUBLIC_BASE_URL = config("MEDIA_PUBLIC_BASE_URL", default="")

# Two media stores (ARCHITECTURE.md section 13): "public" for library photos
# (served directly) and "private" for complaint images (signed URLs only).
if STORAGE_BACKEND == "s3":
    _s3_common = {
        "endpoint_url": AWS_S3_ENDPOINT_URL,
        "access_key": AWS_ACCESS_KEY_ID,
        "secret_key": AWS_SECRET_ACCESS_KEY,
        "file_overwrite": False,
        "default_acl": None,
    }
    _public_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_s3_common,
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "querystring_auth": False,
            "custom_domain": MEDIA_PUBLIC_BASE_URL.removeprefix("https://").rstrip("/") or None,
        },
    }
    _private_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_s3_common,
            "bucket_name": AWS_PRIVATE_BUCKET_NAME,
            "querystring_auth": True,
            "querystring_expire": 600,
        },
    }
else:
    _public_storage = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": MEDIA_ROOT / "public", "base_url": f"{MEDIA_URL}public/"},
    }
    _private_storage = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": MEDIA_ROOT / "private"},
    }

STORAGES = {
    "default": _private_storage,
    "public": _public_storage,
    "private": _private_storage,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Request size limits (SECURITY.md section 7)
DATA_UPLOAD_MAX_MEMORY_SIZE = 1 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --- Django REST Framework (BACKEND_ARCHITECTURE.md section 4) ---------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.core.authentication.JWTAuthentication",),
    # Default deny: public endpoints must opt in with AllowAny (SECURITY.md section 5)
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "EXCEPTION_HANDLER": "apps.core.handlers.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "300/min",
        "login": "10/min",
        "register": "5/min",
        "claim_start": "10/hour",
        "claim_complete": "10/min",
        "password_reset": "10/hour",
        "hold_create": "10/min",
        "upload": "30/hour",
        "webhook": "120/min",
    },
    "NUM_PROXIES": config("NUM_PROXIES", default=None, cast=lambda v: None if v in (None, "") else int(v)),
}

# --- JWT (SECURITY.md section 4) ------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("JWT_SIGNING_KEY"),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
REFRESH_COOKIE_NAME = "lh_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/"

# --- OpenAPI schema (BACKEND_ARCHITECTURE.md #5) -------------------------------
# Public only in local/test; staff-only in production (SECURITY.md section 15).
SCHEMA_PUBLIC = False

SPECTACULAR_SETTINGS = {
    "TITLE": "LibraryHive API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- CORS / CSRF / frontend (SECURITY.md section 11) ----------------------------
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_HEADERS = ("authorization", "content-type", "x-request-id")
CORS_EXPOSE_HEADERS = ("x-request-id", "retry-after")
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost:3000", cast=Csv())

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

ADMIN_URL = config("ADMIN_URL", default="admin/")

# --- Email ----------------------------------------------------------------------
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="LibraryHive <no-reply@localhost>")

# --- Logging (BACKEND_ARCHITECTURE.md section 14, SECURITY.md section 16) --------
LOG_LEVEL = config("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "context": {"()": "apps.core.logging.ContextFilter"},
        "redact": {"()": "apps.core.logging.RedactionFilter"},
    },
    "formatters": {
        "json": {"()": "apps.core.logging.JsonFormatter"},
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["context", "redact"],
        },
    },
    "root": {"handlers": ["stdout"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": False},
        # Request errors are logged by the API exception handler with full context.
        "django.request": {"handlers": ["stdout"], "level": "ERROR", "propagate": False},
        "django.server": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": False},
    },
}

# --- Business configuration (SPEC.md section 6) -----------------------------------
SEAT_HOLD_MINUTES = config("SEAT_HOLD_MINUTES", default=15, cast=int)
MEMBERSHIP_DUE_WINDOW_DAYS = config("MEMBERSHIP_DUE_WINDOW_DAYS", default=3, cast=int)
RENEWAL_RESTART_AFTER_OVERDUE_DAYS = config("RENEWAL_RESTART_AFTER_OVERDUE_DAYS", default=15, cast=int)
MAX_LIBRARY_PHOTOS = config("MAX_LIBRARY_PHOTOS", default=15, cast=int)
MAX_UPLOAD_BYTES = config("MAX_UPLOAD_BYTES", default=5 * 1024 * 1024, cast=int)
MAX_IMAGE_PIXELS = 40_000_000
CLAIM_OTP_MINUTES = config("CLAIM_OTP_MINUTES", default=10, cast=int)
PASSWORD_RESET_MINUTES = config("PASSWORD_RESET_MINUTES", default=30, cast=int)
CLAIM_CODE_DAYS = config("CLAIM_CODE_DAYS", default=7, cast=int)
CLAIM_MAX_ATTEMPTS = config("CLAIM_MAX_ATTEMPTS", default=5, cast=int)
