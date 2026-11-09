"""S3-compatible storage options for Supabase-style providers (config/settings/object_storage.py).

Everything here is offline: django-storages signs private links locally with the (fake) test keys, so no
request ever leaves the machine. The real provider is checked by hand (DEPLOYMENT.md section 6).
"""

from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.core.files.storage import Storage
from django.test import SimpleTestCase
from storages.backends.s3 import S3Storage

from apps.core.storage import content_type_for_key, save_bytes
from config.settings.guard import unsafe_settings_errors
from config.settings.object_storage import PRIVATE_URL_SECONDS, public_base_url_to_domain, s3_storages

ENDPOINT = "https://abcdefgh.storage.supabase.co/storage/v1/s3"
PUBLIC_PREFIX = "https://abcdefgh.supabase.co/storage/v1/object/public/libraryhive-public"
FAKE_ID = "test-access-key-id"
FAKE_SECRET = "test-secret-access-key"


def supabase_stores(**overrides):
    options = {
        "public_bucket": "libraryhive-public",
        "private_bucket": "libraryhive-private",
        "endpoint_url": ENDPOINT,
        "region_name": "ap-south-1",
        "addressing_style": "path",
        "signature_version": "s3v4",
        "access_key": FAKE_ID,
        "secret_key": FAKE_SECRET,
        "public_base_url": PUBLIC_PREFIX,
        **overrides,
    }
    return s3_storages(**options)


def build(kind, **overrides) -> S3Storage:
    return S3Storage(**supabase_stores(**overrides)[kind]["OPTIONS"])


class BothBackendsShareTheProviderSettings(SimpleTestCase):
    def test_endpoint_region_addressing_and_signature_are_applied_to_both(self):
        for kind in ("public", "private"):
            with self.subTest(kind=kind):
                store = build(kind)
                self.assertEqual(store.endpoint_url, ENDPOINT)
                self.assertEqual(store.region_name, "ap-south-1")
                self.assertEqual(store.addressing_style, "path")
                self.assertEqual(store.signature_version, "s3v4")
                self.assertEqual((store.access_key, store.secret_key), (FAKE_ID, FAKE_SECRET))
                self.assertIsNone(store.default_acl)  # Supabase takes no ACL headers
                self.assertFalse(store.file_overwrite)  # a key is never silently replaced

    def test_the_boto_client_really_uses_the_region_and_path_style(self):
        for kind in ("public", "private"):
            with self.subTest(kind=kind):
                client = build(kind).connection.meta.client
                self.assertEqual(client.meta.region_name, "ap-south-1")
                self.assertEqual(client.meta.endpoint_url, ENDPOINT)
                self.assertEqual(client.meta.config.s3["addressing_style"], "path")
                self.assertEqual(client.meta.config.signature_version, "s3v4")

    def test_all_backends_are_the_s3_storage_class(self):
        for entry in supabase_stores().values():
            self.assertEqual(entry["BACKEND"], "storages.backends.s3.S3Storage")


class BucketsAreSeparate(SimpleTestCase):
    def test_public_and_private_buckets_are_not_swapped(self):
        self.assertEqual(build("public").bucket_name, "libraryhive-public")
        self.assertEqual(build("private").bucket_name, "libraryhive-private")

    def test_a_signed_private_link_names_the_private_bucket_only(self):
        path = urlparse(build("private").url("payments/lib/qr/a.webp")).path
        self.assertEqual(path, "/storage/v1/s3/libraryhive-private/payments/lib/qr/a.webp")
        self.assertNotIn("libraryhive-public", path)


class PrivateLinksStaySigned(SimpleTestCase):
    def test_querystring_auth_is_on_and_expiry_is_600_seconds(self):
        private = build("private")
        self.assertTrue(private.querystring_auth)
        self.assertEqual(private.querystring_expire, 600)
        self.assertEqual(PRIVATE_URL_SECONDS, 600)

    def test_the_link_is_pre_signed_v4_for_the_region_and_expires_in_ten_minutes(self):
        url = build("private").url("payments/lib/qr/a.webp", expire=PRIVATE_URL_SECONDS)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}", "https://abcdefgh.storage.supabase.co")
        self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.assertEqual(query["X-Amz-Expires"], ["600"])
        self.assertIn("X-Amz-Signature", query)
        self.assertIn("/ap-south-1/s3/aws4_request", query["X-Amz-Credential"][0])
        self.assertNotIn(FAKE_SECRET, url)  # the secret key is never part of a link

    def test_the_default_expiry_is_also_600_without_an_explicit_argument(self):
        query = parse_qs(urlparse(build("private").url("k.webp")).query)
        self.assertEqual(query["X-Amz-Expires"], ["600"])

    def test_private_storage_never_has_a_public_domain(self):
        self.assertNotIn("custom_domain", supabase_stores()["private"]["OPTIONS"])
        self.assertIsNone(build("private").custom_domain)


class PublicUrlsResolveToThePublicBucket(SimpleTestCase):
    def test_the_url_is_the_full_public_prefix_plus_the_object_key(self):
        url = build("public").url("libraries/abc/photo.webp")
        self.assertEqual(url, f"{PUBLIC_PREFIX}/libraries/abc/photo.webp")
        self.assertIn("/object/public/libraryhive-public/", url)
        self.assertNotIn("libraryhive-private", url)
        self.assertNotIn("?", url)  # unsigned: nothing to expire

    def test_public_storage_does_not_sign(self):
        self.assertFalse(build("public").querystring_auth)

    def test_a_trailing_slash_or_surrounding_space_in_the_base_is_harmless(self):
        for base in (PUBLIC_PREFIX + "/", f"  {PUBLIC_PREFIX}/  "):
            with self.subTest(base=base):
                self.assertEqual(build("public", public_base_url=base).url("a.webp"), f"{PUBLIC_PREFIX}/a.webp")

    def test_the_conversion_keeps_the_bucket_path_and_drops_only_the_scheme(self):
        self.assertEqual(
            public_base_url_to_domain(PUBLIC_PREFIX), "abcdefgh.supabase.co/storage/v1/object/public/libraryhive-public"
        )
        self.assertEqual(public_base_url_to_domain("https://cdn.example.com"), "cdn.example.com")
        self.assertIsNone(public_base_url_to_domain(""))
        self.assertIsNone(public_base_url_to_domain("   "))

    def test_a_plain_http_base_is_refused_not_turned_into_a_broken_link(self):
        with self.assertRaisesMessage(ValueError, "https://"):
            public_base_url_to_domain("http://cdn.example.com/bucket")


class RecordingStorage(Storage):
    """Remembers what `save_bytes` handed over; nothing is stored."""

    def __init__(self):
        self.seen = None

    def _save(self, name, content):
        self.seen = (name, getattr(content, "content_type", None))
        return name

    def get_available_name(self, name, max_length=None):
        return name


class UploadContentType(SimpleTestCase):
    """Found against real Supabase: a `.webp` upload went out as application/octet-stream and got HTTP 415."""

    def test_save_bytes_states_the_content_type_of_each_image_extension(self):
        for key, expected in (
            ("a/b.webp", "image/webp"),
            ("a/b_thumb.WEBP", "image/webp"),
            ("a/b.jpg", "image/jpeg"),
            ("a/b.jpeg", "image/jpeg"),
            ("a/b.png", "image/png"),
        ):
            with self.subTest(key=key):
                store = RecordingStorage()
                save_bytes(store, key, b"data")
                self.assertEqual(store.seen, (key, expected))

    def test_unknown_or_missing_extensions_leave_the_type_unset(self):
        self.assertIsNone(content_type_for_key("a/b.bin"))
        self.assertIsNone(content_type_for_key("a/noextension"))

    def test_s3_gets_image_webp_even_when_the_host_cannot_guess_webp(self):
        store = RecordingStorage()
        save_bytes(store, "payments/lib/qr/a.webp", b"data")
        content = mock.Mock(content_type=store.seen[1])
        with mock.patch("mimetypes.guess_type", return_value=(None, None)):  # Python 3.12 without a webp entry
            params = build("private")._get_write_parameters("payments/lib/qr/a.webp", content)
        self.assertEqual(params["ContentType"], "image/webp")

    def test_without_the_fix_the_same_upload_would_be_octet_stream(self):
        with mock.patch("mimetypes.guess_type", return_value=(None, None)):
            params = build("private")._get_write_parameters("a.webp", mock.Mock(content_type=None))
        self.assertEqual(params["ContentType"], "application/octet-stream")


class OptionalProviderSettings(SimpleTestCase):
    def test_blank_values_fall_back_to_the_library_defaults_for_plain_aws(self):
        options = supabase_stores(endpoint_url="", region_name="", addressing_style="", signature_version="")["public"][
            "OPTIONS"
        ]
        for name in ("endpoint_url", "region_name", "addressing_style", "signature_version"):
            self.assertIsNone(options[name])


SAFE = {
    "debug": False,
    "secret_key": "s" * 60,
    "jwt_signing_key": "j" * 60,
    "allowed_hosts": ["api.libraryhive.example"],
    "cors_allowed_origins": ["https://libraryhive.example"],
    "environment": "production",
    "storage_backend": "s3",
    "public_bucket": "libraryhive-public",
    "private_bucket": "libraryhive-private",
    "aws_access_key_id": FAKE_ID,
    "aws_secret_access_key": FAKE_SECRET,
    "razorpay_key_id": "rzp_live_abc",
    "aws_endpoint_url": ENDPOINT,
    "aws_region_name": "ap-south-1",
    "media_public_base_url": PUBLIC_PREFIX,
}


class ProductionGuardForCustomEndpoints(SimpleTestCase):
    def test_a_complete_supabase_configuration_passes(self):
        self.assertEqual(unsafe_settings_errors(**SAFE), [])

    def test_missing_credentials_are_still_rejected_with_the_endpoint_set(self):
        for field, name in (
            ("aws_access_key_id", "AWS_ACCESS_KEY_ID"),
            ("aws_secret_access_key", "AWS_SECRET_ACCESS_KEY"),
        ):
            errors = unsafe_settings_errors(**{**SAFE, field: ""})
            self.assertEqual(len(errors), 1)
            self.assertIn(name, errors[0])
            self.assertNotIn(FAKE_SECRET, errors[0])

    def test_invalid_bucket_configuration_is_still_rejected(self):
        for field in ("public_bucket", "private_bucket"):
            self.assertIn("needs", unsafe_settings_errors(**{**SAFE, field: ""})[0])
        same = unsafe_settings_errors(**{**SAFE, "private_bucket": SAFE["public_bucket"]})
        self.assertEqual(len(same), 1)
        self.assertIn("different bucket", same[0])

    def test_a_custom_endpoint_needs_a_region(self):
        errors = unsafe_settings_errors(**{**SAFE, "aws_region_name": ""})
        self.assertEqual(len(errors), 1)
        self.assertIn("AWS_S3_REGION_NAME", errors[0])

    def test_a_custom_endpoint_needs_https(self):
        errors = unsafe_settings_errors(**{**SAFE, "aws_endpoint_url": "http://abcdefgh.supabase.co/storage/v1/s3"})
        self.assertEqual(len(errors), 1)
        self.assertIn("AWS_S3_ENDPOINT_URL", errors[0])

    def test_a_custom_endpoint_needs_the_public_base_url_over_https(self):
        missing = unsafe_settings_errors(**{**SAFE, "media_public_base_url": ""})
        self.assertEqual(len(missing), 1)
        self.assertIn("MEDIA_PUBLIC_BASE_URL", missing[0])
        plain = unsafe_settings_errors(**{**SAFE, "media_public_base_url": "http://cdn.example.com/bucket"})
        self.assertEqual(len(plain), 1)
        self.assertIn("https://", plain[0])

    def test_plain_aws_without_an_endpoint_needs_neither_region_nor_base_url(self):
        aws = {**SAFE, "aws_endpoint_url": "", "aws_region_name": "", "media_public_base_url": ""}
        self.assertEqual(unsafe_settings_errors(**aws), [])

    def test_staging_with_local_storage_is_unaffected(self):
        local = {**SAFE, "environment": "staging", "storage_backend": "local", "aws_region_name": ""}
        self.assertEqual(unsafe_settings_errors(**local), [])
