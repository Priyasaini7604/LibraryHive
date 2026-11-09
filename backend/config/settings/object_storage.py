"""S3-compatible object storage options (AWS S3, Supabase Storage, Cloudflare R2, MinIO, ...).

Kept as a pure function so the exact options can be unit tested without importing settings under
`STORAGE_BACKEND=s3`. No network call is made here and no credential is logged or returned in an error.

Two stores, two buckets (ARCHITECTURE.md section 13):

* **public**: library photos. Unsigned URLs. Because django-storages builds
  `https://<custom_domain>/<object key>`, `MEDIA_PUBLIC_BASE_URL` must be the *complete* public prefix of the
  bucket, including the bucket path where the provider has one. For Supabase that is
  `https://<project-ref>.supabase.co/storage/v1/object/public/<public-bucket>`.
* **private**: UPI QR codes and payment screenshots. Always pre-signed (Signature V4), valid for 10 minutes.
"""

PRIVATE_URL_SECONDS = 600


def public_base_url_to_domain(base_url: str) -> str | None:
    """`MEDIA_PUBLIC_BASE_URL` -> django-storages `custom_domain` (host plus optional path, no scheme).

    django-storages always prefixes `https:`, so a plain `http://` base is refused instead of being turned into
    a broken `https://http://...` link.
    """
    value = (base_url or "").strip()
    if not value:
        return None
    if value.lower().startswith("http://"):
        raise ValueError("MEDIA_PUBLIC_BASE_URL must start with https:// (public media is always served over HTTPS).")
    value = value.removeprefix("https://").strip("/")
    return value or None


def s3_storages(
    *,
    public_bucket: str,
    private_bucket: str,
    endpoint_url: str | None,
    region_name: str | None,
    addressing_style: str | None,
    signature_version: str | None,
    access_key: str,
    secret_key: str,
    public_base_url: str,
) -> dict[str, dict]:
    """The `public` and `private` entries for `settings.STORAGES`."""
    common = {
        "endpoint_url": endpoint_url or None,
        "region_name": region_name or None,
        "addressing_style": addressing_style or None,
        "signature_version": signature_version or None,
        "access_key": access_key,
        "secret_key": secret_key,
        "file_overwrite": False,
        # No ACLs: access is decided by the bucket's own policy (Supabase, R2 and others reject ACL headers).
        "default_acl": None,
    }
    return {
        "public": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **common,
                "bucket_name": public_bucket,
                "querystring_auth": False,
                "custom_domain": public_base_url_to_domain(public_base_url),
            },
        },
        "private": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **common,
                "bucket_name": private_bucket,
                "querystring_auth": True,
                "querystring_expire": PRIVATE_URL_SECONDS,
            },
        },
    }
