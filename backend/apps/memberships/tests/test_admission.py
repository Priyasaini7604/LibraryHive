"""Owner-assisted (walk-in) admission and the identity pre-check (#53, #54; SPEC.md 4.6, OFF-01/02/05)."""

import json
import threading
from datetime import timedelta

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.dates import business_today
from apps.core.exceptions import AppError
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications.models import Notification
from apps.payments import gateway
from apps.payments import services as payment_services
from apps.payments.models import Payment
from apps.payments.tests.base import FakeGateway, PaymentTestCase, bookable_library, client_for
from apps.seats import services as seat_services
from apps.seats.models import SeatHold

ADMIT = "/api/v1/owner/admissions/"
LOOKUP = "/api/v1/owner/admissions/lookup/"
PHONE = "+919123456780"


def body(seat, plan, *, phone="9123456780", email="walkin@example.com", method="cash", **extra):
    payload = {
        "student": {"name": "Walk In", "phone": phone, "email": email, "domain_code": ""},
        "seat_id": str(seat.pk),
        "plan_id": str(plan.pk),
        "payment": {"method": method},
    }
    payload.update(extra)
    return payload


class AdmissionTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)

    def admit(self, payload=None, **kwargs):
        return self.owner.post(ADMIT, payload or body(self.seat, self.plan, **kwargs), format="json")

    def test_admits_a_new_walk_in_student_with_membership_and_cash_payment(self):
        response = self.admit()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual((data["student"]["is_offline"], data["student"]["created"]), (True, True))
        user = User.objects.get(pk=data["student"]["id"])
        self.assertEqual(
            (user.phone, user.email, user.role, user.is_offline), (PHONE, "walkin@example.com", "student", True)
        )
        self.assertFalse(user.has_usable_password())

        membership = Membership.objects.get(student=user)
        today = business_today()
        self.assertEqual(
            (membership.source, membership.state, membership.seat_id, membership.created_by_id),
            ("offline", "active", self.seat.pk, self.library.owner.pk),
        )
        self.assertEqual(
            (membership.start_date, membership.next_due_date), (today, today + timedelta(days=self.plan.duration_days))
        )
        self.assertEqual((data["membership"]["status"], data["membership"]["seat"]["label"]), ("active", "A-1"))

        payment = Payment.objects.get(membership=membership)
        self.assertEqual(
            (payment.channel, payment.method, payment.status, payment.purpose, str(payment.amount)),
            ("offline", "cash", "success", "new_membership", "1200.00"),
        )
        self.assertEqual((payment.recorded_by_id, payment.verified_via), (self.library.owner.pk, "manual"))
        self.assertEqual((payment.period_start, payment.period_end), (membership.start_date, membership.next_due_date))
        self.assertTrue(payment.receipt_number.startswith(f"LH-{today.year}-"))
        self.assertEqual(data["payment"]["receipt_number"], payment.receipt_number)
        self.assertTrue(Notification.objects.filter(recipient=user, type="payment_received").exists())
        self.assertTrue(AuditLog.objects.filter(action="membership.create", entity_id=membership.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action="payment.record_offline", entity_id=payment.pk).exists())

    def test_the_seat_derives_as_occupied_afterwards(self):
        self.assertEqual(self.admit().status_code, 201)
        from apps.seats import selectors as seat_selectors

        self.assertTrue(seat_selectors.live_hold_exists(self.seat) is False)
        self.assertTrue(Membership.objects.filter(seat=self.seat, state="active").exists())
        self.assertEqual(
            self.error_code(self.owner.post(ADMIT, body(self.seat, self.plan), format="json")), "SEAT_UNAVAILABLE"
        )

    def test_client_cannot_set_the_amount(self):
        payload = body(self.seat, self.plan)
        payload["payment"]["amount"] = "1.00"
        payload["amount"] = "1.00"
        self.assertEqual(self.admit(payload).status_code, 201)
        self.assertEqual(str(Payment.objects.get().amount), "1200.00")

    def test_existing_online_student_is_linked_not_duplicated(self):
        student = make_student(phone=PHONE, email="existing@example.com")
        response = self.admit(email="")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual((data["student"]["id"], data["student"]["created"]), (str(student.pk), False))
        self.assertEqual(User.objects.filter(phone=PHONE).count(), 1)
        student.refresh_from_db()
        self.assertFalse(student.is_offline)

    def test_email_only_match_links_to_that_student(self):
        student = make_student(email="walkin@example.com")
        response = self.admit()
        self.assertEqual(response.json()["data"]["student"]["id"], str(student.pk))
        student.refresh_from_db()
        self.assertNotEqual(student.phone, PHONE)  # an existing account's contact data is never overwritten

    def test_phone_and_email_of_different_accounts_is_a_conflict(self):
        make_student(phone=PHONE)
        make_student(email="walkin@example.com")
        before = User.objects.count()
        response = self.admit()
        self.assertEqual((response.status_code, self.error_code(response)), (409, "IDENTITY_CONFLICT"))
        self.assertEqual(User.objects.count(), before)
        self.assertFalse(Membership.objects.exists() or Payment.objects.exists())

    def test_an_owner_account_cannot_be_admitted(self):
        make_owner(phone=PHONE)
        response = self.admit()
        self.assertEqual((response.status_code, self.error_code(response)), (409, "CONFLICT"))

    def test_names_are_never_used_for_matching(self):
        make_student(name="Walk In")
        response = self.admit()
        self.assertTrue(response.json()["data"]["student"]["created"])

    def test_already_a_member_here_is_refused_and_nothing_changes(self):
        student = make_student(phone=PHONE)
        make_membership(library=self.library, plan=self.plan, student=student, seat=self.seats[1])
        response = self.admit()
        self.assertEqual((response.status_code, self.error_code(response)), (409, "ALREADY_MEMBER"))
        self.assertEqual(Membership.objects.count(), 1)
        self.assertFalse(Payment.objects.exists())

    def test_an_archived_member_can_be_admitted_again_as_a_new_row(self):
        student = make_student(phone=PHONE)
        make_membership(
            library=self.library,
            plan=self.plan,
            student=student,
            seat=self.seats[1],
            state="archived",
            archived_at=timezone.now(),
        )
        self.assertEqual(self.admit().status_code, 201)
        self.assertEqual(Membership.objects.filter(student=student).count(), 2)

    def test_occupied_disabled_and_student_held_seats_are_unavailable(self):
        make_membership(library=self.library, plan=self.plan, seat=self.seat)
        self.assertEqual(self.error_code(self.admit()), "SEAT_UNAVAILABLE")

        disabled = self.seats[1]
        type(disabled).objects.filter(pk=disabled.pk).update(is_disabled=True)
        self.assertEqual(self.error_code(self.admit(body(disabled, self.plan))), "SEAT_UNAVAILABLE")

        held = self.seats[2]
        self.hold_seat(seat=held)
        before = User.objects.count()
        self.assertEqual(self.error_code(self.admit(body(held, self.plan))), "SEAT_UNAVAILABLE")
        self.assertEqual(User.objects.count(), before)  # the new student was rolled back with everything else

    def test_an_expired_student_hold_does_not_block(self):
        hold = self.hold_seat()
        self.expire(hold)
        self.assertEqual(self.admit().status_code, 201)

    def test_the_owners_manual_hold_is_consumed(self):
        hold = seat_services.place_manual_hold(
            library=self.library, seat_id=self.seat.pk, actor=self.library.owner, reason="Reserved for a regular"
        )
        self.assertEqual(self.admit().status_code, 201)
        hold.refresh_from_db()
        self.assertEqual(hold.status, "completed")
        self.assertTrue(AuditLog.objects.filter(action="hold.consume", entity_id=hold.pk).exists())

    def test_a_failed_admission_leaves_the_manual_hold_in_place(self):
        hold = seat_services.place_manual_hold(
            library=self.library, seat_id=self.seat.pk, actor=self.library.owner, reason="Reserved"
        )
        make_student(phone=PHONE)
        make_student(email="walkin@example.com")
        self.assertEqual(self.admit().status_code, 409)
        hold.refresh_from_db()
        self.assertEqual(hold.status, "pending")

    def test_plan_rules(self):
        type(self.plan).objects.filter(pk=self.plan.pk).update(is_active=False)
        self.assertEqual(self.error_code(self.admit()), "PLAN_INACTIVE")
        _, other_plan, _ = bookable_library()
        self.assertEqual(self.admit(body(self.seat, other_plan)).status_code, 404)

    def test_a_seat_of_another_library_is_a_404(self):
        _, _, other_seats = bookable_library()
        self.assertEqual(self.admit(body(other_seats[0], self.plan)).status_code, 404)
        self.assertFalse(Membership.objects.exists())

    def test_start_date_window(self):
        today = business_today()
        for offset, expected in ((-30, 201), (31, 400)):
            payload = body(self.seat, self.plan, phone=f"91234567{abs(offset):02d}", email=f"x{offset}@example.com")
            payload["start_date"] = str(today + timedelta(days=offset))
            self.assertEqual(self.admit(payload).status_code, expected)
        self.assertEqual(Membership.objects.get().start_date, today - timedelta(days=30))

    def test_paid_at_window_and_method(self):
        now = timezone.now()
        for paid_at, expected in (
            (now + timedelta(hours=1), 400),
            (now - timedelta(days=31), 400),
            (now - timedelta(days=29), 201),
        ):
            payload = body(self.seat, self.plan)
            payload["payment"]["paid_at"] = paid_at.isoformat()
            self.assertEqual(self.admit(payload).status_code, expected)
        self.assertEqual(self.admit(body(self.seats[1], self.plan, method="card", phone="9123456781")).status_code, 400)

    def test_payment_methods(self):
        for index, method in enumerate(("cash", "upi_direct", "bank_transfer")):
            payload = body(
                self.seats[index], self.plan, phone=f"91234567{index:02d}", email=f"m{index}@example.com", method=method
            )
            self.assertEqual(self.admit(payload).status_code, 201)
        self.assertEqual(
            sorted(Payment.objects.values_list("method", flat=True)), ["bank_transfer", "cash", "upi_direct"]
        )

    def test_validation_and_roles(self):
        self.assertEqual(self.admit({"student": {}}).status_code, 400)
        self.assertEqual(self.admit(body(self.seat, self.plan, phone="12345")).status_code, 400)
        self.assertEqual(self.admit(body(self.seat, self.plan, email="not-an-email")).status_code, 400)
        self.assertEqual(
            client_for(self.student).post(ADMIT, body(self.seat, self.plan), format="json").status_code, 403
        )
        self.assertEqual(APIClient().post(ADMIT, body(self.seat, self.plan), format="json").status_code, 401)
        no_library = client_for(make_owner())
        self.assertEqual(no_library.post(ADMIT, body(self.seat, self.plan), format="json").status_code, 409)


class AdmissionLookupTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)

    def lookup(self, **payload):
        return self.owner.post(LOOKUP, payload, format="json")

    def test_no_match(self):
        response = self.lookup(phone="9123456780")
        self.assertEqual(response.json()["data"], {"match": "none"})

    def test_existing_match_is_masked_and_reveals_nothing_else(self):
        student = make_student(phone=PHONE, email="private.person@example.com", name="Private Person")
        data = self.lookup(phone="9123456780").json()["data"]
        self.assertEqual(data["match"], "existing")
        shown = data["student"]
        self.assertEqual(shown["id"], str(student.pk))
        self.assertEqual((shown["masked_phone"], shown["masked_email"]), ("+91******6780", "p***@example.com"))
        self.assertFalse(shown["is_member_here"])
        raw = json.dumps(data)
        self.assertNotIn("9123456780", raw)
        self.assertNotIn("private.person", raw)

    def test_is_member_here(self):
        student = make_student(phone=PHONE)
        make_membership(library=self.library, plan=self.plan, student=student, seat=self.seat)
        self.assertTrue(self.lookup(phone="9123456780").json()["data"]["student"]["is_member_here"])

    def test_conflicting_identity_and_owner(self):
        make_student(phone=PHONE)
        make_student(email="b@example.com")
        response = self.lookup(phone="9123456780", email="b@example.com")
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "IDENTITY_CONFLICT"))
        make_owner(phone="+919123456781")
        self.assertEqual(self.lookup(phone="9123456781").status_code, 409)

    def test_validation_roles_and_no_writes(self):
        self.assertEqual(self.lookup(phone="abc").status_code, 400)
        self.assertEqual(client_for(self.student).post(LOOKUP, {"phone": "9123456780"}, format="json").status_code, 403)
        before = User.objects.count()
        self.lookup(phone="9123456780")
        self.assertEqual(User.objects.count(), before)


class AdmissionRaceTests(TransactionTestCase):
    """An owner admission and an online payment fight for one seat: exactly one student gets it."""

    def setUp(self):
        self.gateway = FakeGateway()
        gateway.use_gateway(self.gateway)
        self.addCleanup(gateway.use_gateway, None)
        self.library, self.plan, self.seats = bookable_library(domain_codes=[], amenity_codes=[])

    def test_admission_versus_online_payment_has_one_winner(self):
        online = make_student()
        seat = self.seats[0]
        hold = seat_services.create_booking_hold(student=online, seat_id=seat.pk, plan_id=self.plan.pk)
        order_id = payment_services.create_order(student=online, hold_id=hold.pk).order_id
        # The hold dies, so the admission may take the seat while the student's money is still in flight.
        SeatHold.objects.filter(pk=hold.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

        from apps.memberships import services as membership_services

        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def run(job):
            try:
                barrier.wait(timeout=15)
                outcomes.append(job())
            except AppError as exc:
                outcomes.append(exc.code)
            finally:
                connection.close()

        def admit():
            membership_services.admit_offline_student(
                library=self.library,
                owner=self.library.owner,
                student={"name": "Walk In", "phone": "9123456780", "email": "w@example.com"},
                seat_id=seat.pk,
                plan_id=self.plan.pk,
                start_date=None,
                payment={"method": "cash"},
            )
            return "admitted"

        def pay():
            payment_services.confirm_payment(order_id=order_id, gateway_payment_id="pay_race", via="webhook")
            return "confirmed"

        threads = [threading.Thread(target=run, args=(job,)) for job in (admit, pay)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        self.assertEqual(Membership.objects.filter(seat=seat, state="active").count(), 1)
        payment = Payment.objects.get(gateway_order_id=order_id)
        winner = Membership.objects.get(seat=seat, state="active")
        if winner.source == "offline":
            self.assertEqual(payment.status, "needs_refund")
        else:
            self.assertEqual(payment.status, "success")
            self.assertIn("SEAT_UNAVAILABLE", outcomes)
