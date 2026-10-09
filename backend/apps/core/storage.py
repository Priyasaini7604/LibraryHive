"""Media storage access (ARCHITECTURE.md section 13, SECURITY.md section 9).

Two stores are configured in settings.STORAGES:
- "public": library photos, served directly (filesystem locally, S3 bucket or CDN in production)
- "private": complaint images, only reachable through short-lived signed URLs

The database stores only object keys, never image binaries.
"""

import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import Storage, storages


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
