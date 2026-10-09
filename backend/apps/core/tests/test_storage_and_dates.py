"""Media storage helpers and business dates."""

import datetime as dt
from unittest import mock

from django.test import SimpleTestCase

from apps.core import dates, storage


class StorageTests(SimpleTestCase):
    def test_random_key_uses_uuid_and_ignores_user_input(self):
        key = storage.random_key("libraries/abc/", "webp", suffix="_thumb")
        self.assertRegex(key, r"^libraries/abc/[0-9a-f]{32}_thumb\.webp$")

    def test_public_storage_saves_and_serves_url(self):
        public = storage.public_storage()
        key = storage.save_bytes(public, storage.random_key("libraries/test", "webp"), b"data")
        try:
            self.assertTrue(public.exists(key))
            self.assertTrue(public.url(key).startswith("/media/public/libraries/test/"))
        finally:
            public.delete(key)

    def test_private_storage_is_separate_from_public(self):
        public, private = storage.public_storage(), storage.private_storage()
        self.assertNotEqual(public.location, private.location)
        key = storage.save_bytes(private, storage.random_key("complaints/test", "webp"), b"secret")
        try:
            self.assertFalse(public.exists(key))
        finally:
            private.delete(key)


class BusinessDateTests(SimpleTestCase):
    def test_business_today_rolls_over_at_midnight_india_time(self):
        # 20:00 UTC on 8 Oct is 01:30 IST on 9 Oct.
        utc_moment = dt.datetime(2026, 10, 8, 20, 0, tzinfo=dt.UTC)
        with mock.patch("django.utils.timezone.now", return_value=utc_moment):
            self.assertEqual(dates.business_today(), dt.date(2026, 10, 9))
            self.assertEqual(dates.business_now().utcoffset(), dt.timedelta(hours=5, minutes=30))
