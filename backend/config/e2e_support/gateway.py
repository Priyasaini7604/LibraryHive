"""A local stand-in for Razorpay used only by the browser end-to-end suite.

It replaces just the two network calls (create an order, list an order's payments). Signature checking is
the real HMAC code from `apps.payments.gateway`, keyed with the dummy secrets in `config.settings.e2e`.
"""

import uuid

from django.conf import settings

from apps.payments.gateway import GatewayOrder, GatewayPayment, HmacVerification


class E2EGateway(HmacVerification):
    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

    def create_order(self, *, amount_paise, receipt, notes):
        return GatewayOrder(order_id=f"order_e2e_{uuid.uuid4().hex[:16]}", amount_paise=amount_paise, currency="INR")

    def fetch_order_payments(self, *, order_id) -> list[GatewayPayment]:
        return []
