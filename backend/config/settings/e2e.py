"""Settings for the Playwright end-to-end suite. Never used by the application itself.

Safety rules, enforced before Django connects to anything:
- The only database is `E2E_DATABASE_URL`, and it must be a local PostgreSQL database named exactly
  `libraryhive_e2e`. `DATABASE_URL` is overwritten with it, so the normal development database named in
  `backend/.env` is never opened by this process.
- Payments use a local fake gateway (`config.e2e_support`). The Razorpay SDK is never called; the Razorpay
  keys below are dummy values and any real key in the environment is ignored.
- Uploads and email stay on this machine (a temporary directory and the console).
"""

import os
import tempfile
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.e2e_guard import e2e_database_errors

_e2e_url = os.environ.get("E2E_DATABASE_URL", "")
_errors = e2e_database_errors(_e2e_url, other_urls=(os.environ.get("DATABASE_URL", ""),))
if _errors:
    raise ImproperlyConfigured("Refusing to start the e2e environment: " + " ".join(_errors))

# Applied before base.py reads its configuration, so nothing from the developer's .env can win.
os.environ["DATABASE_URL"] = _e2e_url
os.environ["ENVIRONMENT"] = "e2e"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_e2e_dummy"
os.environ["RAZORPAY_KEY_SECRET"] = "e2e-dummy-key-secret"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "e2e-dummy-webhook-secret"
os.environ.setdefault("SECRET_KEY", "e2e-only-secret-key-not-used-anywhere-else-0123456789abcdef")
os.environ.setdefault("JWT_SIGNING_KEY", "e2e-only-jwt-signing-key-not-used-anywhere-else-0123456789")

from .base import *  # noqa: E402
from .base import INSTALLED_APPS, REST_FRAMEWORK, STORAGES  # noqa: E402

DEBUG = False
ENVIRONMENT = "e2e"
SCHEMA_PUBLIC = True
INSTALLED_APPS = [*INSTALLED_APPS, "config.e2e_support"]  # installs the fake gateway and adds e2e_prepare

# One dedicated port pair so a running development server is never reused or disturbed.
FRONTEND_URL = os.environ.get("E2E_FRONTEND_URL", "http://127.0.0.1:3010")
CORS_ALLOWED_ORIGINS = [FRONTEND_URL]
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL]
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Fast hashing and no artificial delays: a browser suite logs in many times.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
PASSWORD_RESET_MIN_RESPONSE_SECONDS = 0
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Dummy payment secrets: the checkout stub in the tests signs with this same value, so the real HMAC
# verification code runs. The fake gateway only replaces the two network calls.
RAZORPAY_KEY_ID = "rzp_test_e2e_dummy"
RAZORPAY_KEY_SECRET = "e2e-dummy-key-secret"
RAZORPAY_WEBHOOK_SECRET = "e2e-dummy-webhook-secret"
JOB_TRIGGER_TOKEN = ""

# Throttling has its own tests; the browser suite signs in from one address many times.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {name: "100000/min" for name in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]},
}

_E2E_MEDIA = Path(tempfile.mkdtemp(prefix="libraryhive-e2e-media-"))
STORAGES = {
    **STORAGES,
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _E2E_MEDIA / "private"},
    },
    "public": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _E2E_MEDIA / "public", "base_url": "/media/public/"},
    },
    "private": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _E2E_MEDIA / "private"},
    },
}
