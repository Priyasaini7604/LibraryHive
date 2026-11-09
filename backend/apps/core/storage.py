"""Media storage access (ARCHITECTURE.md section 13, SECURITY.md section 9).

Two stores are configured in settings.STORAGES:
- "public": library photos, served directly (filesystem locally, S3 bucket or CDN in production)
- "private": complaint images, only reachable through short-lived signed URLs

The database stores only object keys, never image binaries.
"""

import uuid

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, storages
from django.urls import reverse


def public_storage() -> Storage:
    return storages["public"]


def private_storage() -> Storage:
    return storages["private"]


def random_key(prefix: str, extension: str, *, suffix: str = "") -> str:
    """UUID-based object key; user input never becomes part of a path."""
    clean_prefix = prefix.strip("/")
    return f"{clean_prefix}/{uuid.uuid4().hex}{suffix}.{extension.lstrip('.')}"


def save_bytes(storage: Storage, key: str, data: bytes) -> str:
    """Store bytes under `key` and return the key actually used."""
    return storage.save(key, ContentFile(data))


PRIVATE_FILE_SALT = "libraryhive.private-file"
PRIVATE_FILE_SECONDS = 600


def private_file_url(key: str, *, request=None) -> str:
    """A short-lived link to one private object (payment QR codes and screenshots).

    On S3-compatible storage this is the provider's pre-signed URL (10 minutes, `querystring_auth`). On the local
    filesystem (development and tests) there is no such thing, so the link is a signed token for
    `core.views.PrivateFileView`, which is switched off when `STORAGE_BACKEND=s3`. Either way the link expires,
    and who may ask for one is decided by the view that calls this, not by the link.
    """
    if settings.STORAGE_BACKEND == "s3":
        return private_storage().url(key, expire=PRIVATE_FILE_SECONDS)
    token = signing.dumps({"k": key}, salt=PRIVATE_FILE_SALT, compress=True)
    path = reverse("private-file", args=[token])
    return request.build_absolute_uri(path) if request is not None else path


def read_private_file_key(token: str) -> str | None:
    """The key inside an unexpired local-file token, or None if it is forged or expired."""
    try:
        data = signing.loads(token, salt=PRIVATE_FILE_SALT, max_age=PRIVATE_FILE_SECONDS)
    except signing.BadSignature:
        return None
    key = data.get("k") if isinstance(data, dict) else None
    return key if isinstance(key, str) else None
