"""The payment gateway boundary (BACKEND_ARCHITECTURE.md section 10).

This is the **only** module that imports the Razorpay SDK, and it does so lazily, so the rest of the
application (and every automated test) runs without network access.

Signature checks are plain HMAC-SHA256 with constant-time comparison and live in `HmacVerification`, which the
real and the fake gateway share, so tests exercise the real cryptography. An empty secret never verifies:
a missing configuration must fail closed, not accept everything.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings

from apps.core.exceptions import GatewayError

logger = logging.getLogger("apps.payments")


@dataclass(frozen=True)
class GatewayOrder:
    order_id: str
    amount_paise: int
    currency: str


@dataclass(frozen=True)
class GatewayPayment:
    payment_id: str
    status: str  # "captured", "failed", "authorized", "created" ...
    amount_paise: int


class PaymentGateway(Protocol):
    key_id: str

    def create_order(self, *, amount_paise: int, receipt: str, notes: dict) -> GatewayOrder: ...

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool: ...

    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> bool: ...

    def fetch_order_payments(self, *, order_id: str) -> list[GatewayPayment]: ...


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class HmacVerification:
    """Razorpay's two signature schemes. Both fail closed when the secret is not configured."""

    key_secret: str
    webhook_secret: str

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        if not self.key_secret or not order_id or not payment_id or not signature:
            return False
        expected = _hmac_hex(self.key_secret, f"{order_id}|{payment_id}".encode())
        return hmac.compare_digest(expected, signature)

    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> bool:
        if not self.webhook_secret or not signature:
            return False
        return hmac.compare_digest(_hmac_hex(self.webhook_secret, raw_body), signature)


class RazorpayGateway(HmacVerification):
    """Razorpay over its official SDK. Secrets come from the environment only."""

    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        self._client = None

    def _sdk(self):
        if self._client is None:
            if not (self.key_id and self.key_secret):
                logger.error("Payment gateway is not configured")
                raise GatewayError()
            import razorpay  # only here: no other module imports the SDK

            self._client = razorpay.Client(auth=(self.key_id, self.key_secret))
            self._client.set_app_details({"title": "LibraryHive", "version": settings.APP_VERSION})
        return self._client

    def create_order(self, *, amount_paise: int, receipt: str, notes: dict) -> GatewayOrder:
        try:
            order = self._sdk().order.create(
                {"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes}
            )
            return GatewayOrder(order_id=order["id"], amount_paise=int(order["amount"]), currency=order["currency"])
        except GatewayError:
            raise
        except Exception as exc:
            logger.error("Gateway order creation failed", extra={"error_type": type(exc).__name__})
            raise GatewayError() from exc

    def fetch_order_payments(self, *, order_id: str) -> list[GatewayPayment]:
        try:
            items = self._sdk().order.payments(order_id).get("items", [])
            return [
                GatewayPayment(payment_id=item["id"], status=item["status"], amount_paise=int(item["amount"]))
                for item in items
            ]
        except GatewayError:
            raise
        except Exception as exc:
            logger.error("Gateway order lookup failed", extra={"error_type": type(exc).__name__})
            raise GatewayError() from exc


_override: PaymentGateway | None = None


def get_gateway() -> PaymentGateway:
    """The gateway services use. Tests install a fake with `use_gateway()`."""
    return _override or RazorpayGateway()


def use_gateway(gateway: PaymentGateway | None) -> None:
    """Install (or, with None, remove) a replacement gateway. For automated tests only."""
    global _override
    _override = gateway
