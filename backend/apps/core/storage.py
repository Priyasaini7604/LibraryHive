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


IMAGE_CONTENT_TYPES = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}


def content_type_for_key(key: str) -> str | None:
    """Image content type from the key's extension, or None for anything else."""
    return IMAGE_CONTENT_TYPES.get(key.rsplit(".", 1)[-1].lower()) if "." in key else None


def save_bytes(storage: Storage, key: str, data: bytes) -> str:
    """Store bytes under `key` and return the key actually used.

    The content type is stated explicitly. django-storages otherwise guesses it from the file name with Python's
    `mimetypes`, which does not know `.webp` before Python 3.13 (nor on a host without a mime.types file); the
    upload would then go out as `application/octet-stream`, which Supabase Storage refuses with HTTP 415 and which
    would make a public photo download instead of display.
    """
    content = ContentFile(data)
    content_type = content_type_for_key(key)
    if content_type:
        content.content_type = content_type  # read by S3Storage; ignored by the filesystem storage
    return storage.save(key, content)


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
