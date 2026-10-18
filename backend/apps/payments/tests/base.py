"""Test support for payments: a fake gateway and ready-made fixtures.

`FakeGateway` replaces only the network calls (create an order, list an order's payments). Signature checking is
the real HMAC code from `apps.payments.gateway`, keyed with the dummy secrets in `config/settings/test.py`, so
forged, wrong-secret and valid signatures are all tested against the production verification logic.
"""

import hashlib
import hmac
import itertools
import json
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import GatewayError
from apps.core.tests.factories import make_student
from apps.libraries.tests.base import make_library, make_plan
from apps.payments import gateway
from apps.payments.gateway import GatewayOrder, GatewayPayment, HmacVerification
from apps.seats import services as seat_services
from apps.seats.models import Seat, SeatHold

_order_numbers = itertools.count(1)
_event_numbers = itertools.count(1)


class FakeGateway(HmacVerification):
    key_id = "rzp_test_unit_tests"

    def __init__(self):
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        self.orders: list[dict] = []
        self.captured: dict[str, list[GatewayPayment]] = {}
        self.fail_orders = False
        self.fail_lookups = False

    def create_order(self, *, amount_paise, receipt, notes):
        if self.fail_orders:
            raise GatewayError()
        order = GatewayOrder(
            order_id=f"order_fake_{next(_order_numbers):06d}", amount_paise=amount_paise, currency="INR"
        )
        self.orders.append({"order": order, "receipt": receipt, "notes": notes})
        return order

    def fetch_order_payments(self, *, order_id):
        if self.fail_lookups:
            raise GatewayError()
        return self.captured.get(order_id, [])

    # helpers used only by tests -----------------------------------------------------------------------
    def capture(self, order_id, payment_id, amount_paise):
        self.captured.setdefault(order_id, []).append(GatewayPayment(payment_id, "captured", amount_paise))

    def checkout_signature(self, order_id, payment_id, secret=None):
        key = (secret or self.key_secret).encode()
        return hmac.new(key, f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    def webhook_signature(self, raw_body: bytes, secret=None):
        return hmac.new((secret or self.webhook_secret).encode(), raw_body, hashlib.sha256).hexdigest()


def captured_event(order_id, payment_id, amount_paise=None, event="payment.captured"):
    entity = {"id": payment_id, "order_id": order_id, "status": "captured"}
    if amount_paise is not None:
        entity["amount"] = amount_paise
    return {"event": event, "payload": {"payment": {"entity": entity}}}


def failed_event(order_id, payment_id, description="Card declined"):
    entity = {"id": payment_id, "order_id": order_id, "error_description": description}
    return {"event": "payment.failed", "payload": {"payment": {"entity": entity}}}


def bookable_library(*, seats=3, **kwargs):
    """A published library: a plan plus real seats (the publish rule counts them)."""
    library = make_library(**kwargs)
    plan = make_plan(library)
    seat_services.create_seats(library=library, actor=library.owner, specs=seat_services.grid_specs(["A"], seats))
    library.refresh_from_db()
    return library, plan, list(Seat.objects.filter(library=library).order_by("position"))


def client_for(user):
    client = APIClient()
    client.force_authenticate(type(user).objects.get(pk=user.pk))
    return client


class PaymentTestCase(TestCase):
    """A library with one plan (1200.00 for 30 days), three seats, a student and a fake gateway."""

    def setUp(self):
        cache.clear()
        self.gateway = FakeGateway()
        gateway.use_gateway(self.gateway)
        self.addCleanup(gateway.use_gateway, None)
        self.library, self.plan, self.seats = bookable_library()
        self.seat = self.seats[0]
        self.student = make_student()

    def hold_seat(self, student=None, seat=None):
        return seat_services.create_booking_hold(
            student=student or self.student, seat_id=(seat or self.seat).pk, plan_id=self.plan.pk
        )

    def order_for(self, hold, student=None):
        """Create the order through the API as the student and return the response data."""
        response = client_for(student or hold.student).post(
            "/api/v1/payments/orders/", {"hold_id": str(hold.pk)}, format="json"
        )
        assert response.status_code == 201, response.content
        return response.json()["data"]

    def verify(self, order_id, payment_id, *, student=None, signature=None, **extra):
        return client_for(student or self.student).post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature or self.gateway.checkout_signature(order_id, payment_id),
                **extra,
            },
            format="json",
        )

    def webhook(self, body: dict | bytes, *, signature=None, event_id=None, headers=True, enforce_csrf=False):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        client = APIClient(enforce_csrf_checks=enforce_csrf)
        extra = {}
        if headers:
            extra["HTTP_X_RAZORPAY_SIGNATURE"] = (
                signature if signature is not None else self.gateway.webhook_signature(raw)
            )
            extra["HTTP_X_RAZORPAY_EVENT_ID"] = event_id if event_id is not None else f"evt_{next(_event_numbers):06d}"
        return client.post("/api/v1/payments/webhook/razorpay/", raw, content_type="application/json", **extra)

    def paid(self, order_id, payment_id="pay_ok_1", amount_paise=120000):
        """Deliver a valid payment.captured webhook for an order."""
        return self.webhook(captured_event(order_id, payment_id, amount_paise))

    def expire(self, hold):
        SeatHold.objects.filter(pk=hold.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    def error_code(self, response):
        return response.json()["error_code"]
