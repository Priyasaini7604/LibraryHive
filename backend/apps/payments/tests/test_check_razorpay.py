"""The `check_razorpay` operator command: its checks run against a fake provider here, never the real one."""

import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.payments import gateway
from apps.payments.models import Payment

from .base import FakeGateway


def run():
    out = io.StringIO()
    call_command("check_razorpay", stdout=out)
    return out.getvalue()


class CheckRazorpayTests(TestCase):
    def setUp(self):
        self.fake = FakeGateway()
        gateway.use_gateway(self.fake)
        self.addCleanup(gateway.use_gateway, None)

    def test_passes_and_prints_no_secret(self):
        text = run()
        self.assertIn("All checks passed.", text)
        self.assertIn("created a test order of Rs 1", text)
        self.assertIn("a forged signature is rejected", text)
        from django.conf import settings

        for secret in (settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_WEBHOOK_SECRET):
            self.assertNotIn(secret, text)
        self.assertEqual(self.fake.orders[0]["order"].amount_paise, 100)  # one rupee, nothing more

    def test_writes_nothing_to_the_database(self):
        run()
        self.assertFalse(Payment.objects.exists())

    def test_a_provider_failure_is_reported_and_exits_non_zero(self):
        self.fake.fail_orders = True
        with self.assertRaises(CommandError) as raised:
            run()
        self.assertIn("failed", str(raised.exception))

    @override_settings(RAZORPAY_KEY_ID="rzp_live_abcdef")
    def test_refuses_live_keys(self):
        with self.assertRaises(CommandError) as raised:
            run()
        self.assertIn("LIVE", str(raised.exception))
        self.assertEqual(self.fake.orders, [])  # nothing was called

    @override_settings(RAZORPAY_KEY_SECRET="")
    def test_refuses_without_keys(self):
        with self.assertRaises(CommandError):
            run()

    @override_settings(RAZORPAY_WEBHOOK_SECRET="")
    def test_reports_a_missing_webhook_secret(self):
        with self.assertRaises(CommandError):
            run()
