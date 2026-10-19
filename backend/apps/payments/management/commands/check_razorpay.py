"""Check the configured Razorpay TEST keys against the real provider: `python manage.py check_razorpay`.

What it proves, and what it does not:
- It calls the real Razorpay API: it creates one 1-rupee order and reads it back. That shows the key id and secret
  are valid and that our adapter talks to the provider correctly.
- It exercises our checkout and webhook signature code with your configured secrets. The signatures are produced
  here, so this shows the verification code and the secrets agree; it is not an event sent by Razorpay.
- It does NOT complete a payment (that needs the checkout window) and does NOT prove that Razorpay can reach your
  webhook URL. See `docs` in IMPLEMENTATION_PLAN.md (T14) for the manual part.

It writes nothing to the database, never prints a secret, and refuses live keys.
"""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.payments import gateway


def _sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class Command(BaseCommand):
    help = (
        "Verify the Razorpay test keys with one real 1-rupee test order and a signature self-test. Prints no secrets."
    )

    def handle(self, *args, **options):
        failures: list[str] = []

        def report(ok: bool, text: str) -> None:
            self.stdout.write(("  PASS  " if ok else "  FAIL  ") + text)
            if not ok:
                failures.append(text)

        names = ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET")
        missing = [name for name in names if not getattr(settings, name, "")]
        report(
            not missing,
            "configuration: all three variables are set" if not missing else f"missing: {', '.join(missing)}",
        )
        if "RAZORPAY_KEY_ID" in missing or "RAZORPAY_KEY_SECRET" in missing:
            raise CommandError("Set the Razorpay test keys in backend/.env first.")

        key_id = settings.RAZORPAY_KEY_ID
        if key_id.startswith("rzp_live_"):
            raise CommandError("These are LIVE keys. This check only runs with test keys (rzp_test_...).")
        report(key_id.startswith("rzp_test_"), "key id is a test-mode key (rzp_test_...)")

        client = gateway.get_gateway()
        order_id = None
        try:
            order = client.create_order(
                amount_paise=100,
                receipt=f"LHCHECK{secrets.token_hex(6)}",
                notes={"purpose": "LibraryHive configuration check, safe to ignore"},
            )
            order_id = order.order_id
            report(
                order.amount_paise == 100 and order.currency == "INR" and order_id.startswith("order_"),
                f"real provider call: created a test order of Rs 1 ({order_id})",
            )
        except Exception as exc:  # report any provider or network error without exposing credentials
            report(
                False, f"real provider call failed: {type(exc).__name__} (check the key id and secret, and the network)"
            )

        if order_id:
            try:
                payments = client.fetch_order_payments(order_id=order_id)
                report(payments == [], "real provider call: read the order back (no payments yet, as expected)")
            except Exception as exc:
                report(False, f"reading the order back failed: {type(exc).__name__}")

            good = _sign(settings.RAZORPAY_KEY_SECRET, f"{order_id}|pay_check".encode())
            report(
                client.verify_checkout_signature(order_id=order_id, payment_id="pay_check", signature=good),
                "checkout signature: a correctly signed result is accepted",
            )
            report(
                not client.verify_checkout_signature(order_id=order_id, payment_id="pay_other", signature=good),
                "checkout signature: the same signature for another payment is rejected",
            )
            report(
                not client.verify_checkout_signature(order_id=order_id, payment_id="pay_check", signature="0" * 64),
                "checkout signature: a forged signature is rejected",
            )

        if settings.RAZORPAY_WEBHOOK_SECRET:
            body = b'{"event":"payment.captured","payload":{}}'
            good_hook = _sign(settings.RAZORPAY_WEBHOOK_SECRET, body)
            report(
                client.verify_webhook_signature(raw_body=body, signature=good_hook),
                "webhook signature: a correctly signed body is accepted",
            )
            report(
                not client.verify_webhook_signature(raw_body=body + b" ", signature=good_hook),
                "webhook signature: a changed body is rejected",
            )
            report(
                not client.verify_webhook_signature(raw_body=body, signature=""),
                "webhook signature: a missing signature is rejected",
            )

        self.stdout.write("")
        self.stdout.write(
            "Not covered here: completing a payment in the checkout window, "
            "and Razorpay delivering a webhook to your server."
        )
        if failures:
            raise CommandError(f"{len(failures)} check(s) failed.")
        self.stdout.write(self.style.SUCCESS("All checks passed."))
