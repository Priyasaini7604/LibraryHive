from django.test import SimpleTestCase

from apps.accounts.phone import InvalidPhone, mask_email, normalize_phone


class PhoneNormalisationTests(SimpleTestCase):
    def test_common_indian_formats_normalise_to_e164(self):
        for raw in ("9876543210", "98765 43210", "+91 98765 43210", "+91-98765-43210", "09876543210", "919876543210"):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), "+919876543210")

    def test_invalid_or_foreign_numbers_rejected(self):
        for raw in ("", "12345", "+1 202 555 0143", "abcdefghij", "0000000000"):
            with self.subTest(raw=raw), self.assertRaises(InvalidPhone):
                normalize_phone(raw)

    def test_mask_email(self):
        self.assertEqual(mask_email("rahul.sharma@gmail.com"), "r***@gmail.com")
        self.assertIsNone(mask_email(None))
