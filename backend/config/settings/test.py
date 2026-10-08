"""Settings for the automated test suite (`python manage.py test`).

Tests run against PostgreSQL (the Docker database locally, a service container
in CI); Django creates and drops a separate test database.
"""

import copy
import tempfile
from pathlib import Path

from .base import *
from .base import LOGGING, STORAGES

DEBUG = False
ENVIRONMENT = "test"
SCHEMA_PUBLIC = True

# Fast hashing for tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Keep test output readable; tests that check log lines use assertLogs.
LOGGING = copy.deepcopy(LOGGING)
LOGGING["root"]["level"] = "CRITICAL"
for _logger in LOGGING["loggers"].values():
    _logger["level"] = "CRITICAL"

# Uploaded files go to a throwaway directory.
_TEST_MEDIA = Path(tempfile.mkdtemp(prefix="libraryhive-test-media-"))
STORAGES = {
    **STORAGES,
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _TEST_MEDIA / "private"},
    },
    "public": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _TEST_MEDIA / "public", "base_url": "/media/public/"},
    },
    "private": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": _TEST_MEDIA / "private"},
    },
}
