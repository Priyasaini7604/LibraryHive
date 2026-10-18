"""Renewals: the D5 date arithmetic, the owner-recorded renewal (#48) and the online renewal (#41, #42, webhook)."""

from datetime import date, timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from apps.core.dates import business_today
from apps.core.models import AuditLog
from apps.libraries.tests.base import make_plan
from apps.memberships import services
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for

ORDERS = "/api/v1/payments/orders/"
TODAY = date(2026, 10, 18)


def make_overdue(membership, days):
    due = business_today() - timedelta(days=days)
    Membership.objects.filter(pk=membership.pk).update(start_date=due - timedelta(days=30), next_due_date=due)


class RenewalArithmeticTests(SimpleTestCase):
    def period(self, due_offset):
        return services.renewal_period(next_due_date=TODAY + timedelta(days=due_offset), duration_days=30, today=TODAY)

    def test_on_time_and_early_renewals_continue_from_the_old_due_date(self):
        for offset in (0, 3, 7):
            start, end = self.period(offset)
            self.assertEqual((start, end), (TODAY + timedelta(days=offset), TODAY + timedelta(days=offset + 30)))

    def test_overdue_up_to_15_days_still_continues_from_the_old_due_date(self):
        for overdue in (1, 10, 15):
            start, end = self.period(-overdue)
            self.assertEqual(start, TODAY - timedelta(days=overdue))
            self.assertEqual(end, start + timedelta(days=30))

    def test_more_than_15_days_overdue_restarts_today(self):
        for overdue in (16, 40):
            self.assertEqual(self.period(-overdue), (TODAY, TODAY + timedelta(days=30)))


class OfflineRenewalTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)
        self.today = business_today()
        self.membership = make_membership(
            library=self.library, plan=self.plan, student=self.student, seat=self.seat, due_in=2
        )

    def renew(self, membership=None, **payload):
        payload.setdefault("method", "cash")
        url = f"/api/v1/owner/members/{(membership or self.membership).pk}/renewals/"
        return self.owner.post(url, payload, format="json")

    def test_renewal_extends_from_the_old_due_date_and_records_the_payment(self):
        old_due = self.membership.next_due_date
        response = self.renew(notes="Paid at the desk")
        self.assertEqual(response.status_code, 201, response.content)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.next_due_date, old_due + timedelta(days=30))
        payment = Payment.objects.get()
        self.assertEqual(
            (payment.purpose, payment.channel, payment.method, payment.status, str(payment.amount)),
            ("renewal", "offline", "cash", "success", "1200.00"),
        )
        self.assertEqual((payment.period_start, payment.period_end), (old_due, old_due + timedelta(days=30)))
        self.assertEqual((payment.recorded_by_id, payment.membership_id), (self.library.owner.pk, self.membership.pk))
        self.assertEqual(payment.notes, "Paid at the desk")
        data = response.json()["data"]
        self.assertEqual(data["payment"]["receipt_number"], payment.receipt_number)
        self.assertEqual(data["membership"]["next_due_date"], str(old_due + timedelta(days=30)))
        self.assertTrue(AuditLog.objects.filter(action="membership.renew", entity_id=self.membership.pk).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.student, type="payment_received").exists())

    def test_overdue_beyond_15_days_restarts_today_and_the_seat_is_kept(self):
        make_overdue(self.membership, 20)
        self.renew()
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.next_due_date, self.today + timedelta(days=30))
        self.assertEqual((self.membership.seat_id, self.membership.state), (self.seat.pk, "active"))

    def test_plan_change_uses_the_new_plan_price_and_duration(self):
        longer = make_plan(self.library, name="Quarterly", duration_days=90, price="3000.00")
        old_due = self.membership.next_due_date
        self.assertEqual(self.renew(plan_id=str(longer.pk)).status_code, 201)
        self.membership.refresh_from_db()
        self.assertEqual(
            (self.membership.plan_id, self.membership.next_due_date), (longer.pk, old_due + timedelta(days=90))
        )
        self.assertEqual(str(Payment.objects.get().amount), "3000.00")

    def test_the_client_cannot_set_the_amount(self):
        self.renew(amount="1.00")
        self.assertEqual(str(Payment.objects.get().amount), "1200.00")

    def test_inactive_plan_and_foreign_plan(self):
        type(self.plan).objects.filter(pk=self.plan.pk).update(is_active=False)
        response = self.renew()
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "PLAN_INACTIVE"))
        _, other_plan, _ = bookable_library()
        self.assertEqual(self.renew(plan_id=str(other_plan.pk)).status_code, 404)
        self.assertFalse(Payment.objects.exists())

    def test_archived_membership(self):
        Membership.objects.filter(pk=self.membership.pk).update(state="archived", archived_at=timezone.now())
        response = self.renew()
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "MEMBERSHIP_ARCHIVED"))

    def test_paid_at_window_and_method(self):
        now = timezone.now()
        self.assertEqual(self.renew(paid_at=(now + timedelta(hours=2)).isoformat()).status_code, 400)
        self.assertEqual(self.renew(paid_at=(now - timedelta(days=31)).isoformat()).status_code, 400)
        self.assertEqual(self.renew(method="gateway").status_code, 400)
        self.assertFalse(Payment.objects.exists())
        self.membership.refresh_from_db()
        self.assertEqual(
            self.membership.next_due_date, self.today + timedelta(days=2)
        )  # a refused renewal changes nothing
        self.assertEqual(self.renew(paid_at=(now - timedelta(days=5)).isoformat()).status_code, 201)

    def test_another_librarys_member_is_a_404_and_roles(self):
        other_library, other_plan, other_seats = bookable_library()
        theirs = make_membership(library=other_library, plan=other_plan, seat=other_seats[0])
        self.assertEqual(self.renew(theirs).status_code, 404)
        self.assertEqual(
            client_for(self.student)
            .post(f"/api/v1/owner/members/{self.membership.pk}/renewals/", {"method": "cash"}, format="json")
            .status_code,
            403,
        )


class OnlineRenewalTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.today = business_today()
        self.membership = make_membership(
            library=self.library, plan=self.plan, student=self.student, seat=self.seat, due_in=5
        )

    def order(self, student=None, **payload):
        payload.setdefault("membership_id", str(self.membership.pk))
        return client_for(student or self.student).post(ORDERS, payload, format="json")

    def test_creates_a_pending_renewal_order_with_the_plan_price(self):
        response = self.order()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual((data["amount_paise"], data["currency"]), (120000, "INR"))
        payment = Payment.objects.get(pk=data["payment_id"])
        self.assertEqual(
            (payment.status, payment.purpose, payment.channel, payment.membership_id, payment.hold_id),
            ("pending", "renewal", "online", self.membership.pk, None),
        )
        self.assertEqual(self.gateway.orders[0]["notes"]["membership_id"], str(self.membership.pk))

    def test_client_amount_is_ignored(self):
        self.order(amount="1.00", amount_paise=100)
        self.assertEqual(self.gateway.orders[0]["order"].amount_paise, 120000)

    def test_renewal_is_not_open_more_than_7_days_before_the_due_date(self):
        Membership.objects.filter(pk=self.membership.pk).update(next_due_date=self.today + timedelta(days=8))
        response = self.order()
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "RENEWAL_NOT_OPEN"))
        Membership.objects.filter(pk=self.membership.pk).update(next_due_date=self.today + timedelta(days=7))
        self.assertEqual(self.order().status_code, 201)

    def test_overdue_members_can_renew(self):
        make_overdue(self.membership, 3)
        self.assertEqual(self.order().status_code, 201)

    def test_archived_foreign_and_unowned_memberships(self):
        Membership.objects.filter(pk=self.membership.pk).update(state="archived", archived_at=timezone.now())
        self.assertEqual(self.order().json()["error_code"], "MEMBERSHIP_ARCHIVED")
        Membership.objects.filter(pk=self.membership.pk).update(state="active", archived_at=None)
        from apps.core.tests.factories import make_student

        self.assertEqual(self.order(student=make_student()).status_code, 404)
        self.assertFalse(Payment.objects.exists())

    def test_plan_change_must_be_active_and_in_the_same_library(self):
        other = make_plan(self.library, name="Half", duration_days=15, price="700.00")
        response = self.order(plan_id=str(other.pk))
        self.assertEqual(response.json()["data"]["amount_paise"], 70000)
        type(other).objects.filter(pk=other.pk).update(is_active=False)
        self.assertEqual(self.order(plan_id=str(other.pk)).json()["error_code"], "PLAN_INACTIVE")
        _, foreign, _ = bookable_library()
        self.assertEqual(self.order(plan_id=str(foreign.pk)).status_code, 404)
        self.assertEqual(self.order(plan_id="nope").status_code, 400)

    def test_exactly_one_of_hold_or_membership(self):
        from apps.core.tests.factories import make_student

        hold = self.hold_seat(student=make_student(), seat=self.seats[1])
        self.assertEqual(self.order(hold_id=str(hold.pk)).status_code, 400)
        self.assertEqual(client_for(self.student).post(ORDERS, {}, format="json").status_code, 400)

    def test_gateway_failure_leaves_nothing_behind(self):
        self.gateway.fail_orders = True
        self.assertEqual(self.order().status_code, 502)
        self.assertFalse(Payment.objects.exists())

    def test_verified_payment_extends_the_membership_once(self):
        order = self.order().json()["data"]
        old_due = self.membership.next_due_date
        response = self.verify(order["order_id"], "pay_renew_1")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["payment"]["status"], "success")
        self.assertEqual(data["membership"]["id"], str(self.membership.pk))
        self.membership.refresh_from_db()
        expected = old_due + timedelta(days=30)
        self.assertEqual(self.membership.next_due_date, expected)
        payment = Payment.objects.get()
        self.assertEqual(
            (payment.period_start, payment.period_end, payment.verified_via), (old_due, expected, "checkout")
        )

        # Webhook and a repeated verify afterwards change nothing.
        self.assertEqual(self.paid(order["order_id"], "pay_renew_1").status_code, 200)
        self.assertEqual(self.verify(order["order_id"], "pay_renew_1").status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.next_due_date, expected)
        self.assertEqual(Notification.objects.filter(type="payment_received", recipient=self.student).count(), 1)
        self.assertEqual(Notification.objects.filter(type="payment_received", recipient=self.library.owner).count(), 1)

    def test_a_forged_signature_never_extends(self):
        order = self.order().json()["data"]
        response = self.verify(order["order_id"], "pay_x", signature="0" * 64)
        self.assertEqual(response.status_code, 400)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.next_due_date, self.today + timedelta(days=5))
        self.assertEqual(Payment.objects.get().status, "pending")

    def test_the_webhook_confirms_a_renewal_too(self):
        order = self.order().json()["data"]
        self.assertEqual(self.paid(order["order_id"], "pay_hook_1").status_code, 200)
        self.assertEqual(Payment.objects.get().status, "success")

    def test_money_arriving_after_archival_needs_a_refund_and_never_reopens_the_membership(self):
        order = self.order().json()["data"]
        Membership.objects.filter(pk=self.membership.pk).update(state="archived", archived_at=timezone.now())
        response = self.verify(order["order_id"], "pay_late_1")
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "SEAT_LOST_REFUND_PENDING"))
        self.assertEqual(Payment.objects.get().status, "needs_refund")
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.state, "archived")

    def test_reconcile_cancels_an_abandoned_renewal_order(self):
        from apps.payments import services as payment_services

        self.order()
        Payment.objects.update(created_at=timezone.now() - timedelta(hours=2))
        counts = payment_services.reconcile_stale_orders()
        self.assertEqual((counts["cancelled"], counts["errors"]), (1, 0))
        self.assertEqual(Payment.objects.get().status, "cancelled")
