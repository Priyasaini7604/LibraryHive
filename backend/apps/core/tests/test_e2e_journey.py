"""One end-to-end journey through the real API: every request is made as a signed-in user would make it.

No forced authentication: accounts are registered and logged in through the auth endpoints and the access token
is sent as a bearer header, exactly as the frontend does. Only the payment gateway's network calls are replaced
(`FakeGateway`); its signature checks are the production code with dummy secrets. This is local integration, not
a real Razorpay test-mode payment.
"""

import json
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.dates import business_today
from apps.core.tests.factories import make_student
from apps.libraries.tests.base import LIBRARY_PAYLOAD
from apps.payments import gateway
from apps.payments.tests.base import FakeGateway, captured_event

PASSWORD = "Str0ng-pass-123"


def signed_in(client: APIClient, access: str) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def unwrap(response, status=None):
    if status is not None:
        assert response.status_code == status, (response.status_code, response.content)
    body = response.json()
    return body["data"]


class JourneyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.gateway = FakeGateway()
        gateway.use_gateway(self.gateway)
        self.addCleanup(gateway.use_gateway, None)

    def auth(self, action, payload):
        client = APIClient()
        response = client.post(f"/api/v1/auth/{action}/", payload, format="json", HTTP_ORIGIN=settings.FRONTEND_URL)
        return unwrap(response, 201 if action == "register" else 200)

    def test_owner_sets_up_students_book_and_everyone_is_notified(self):
        # --- An owner registers, signs in and opens a library -------------------------------------------
        self.auth(
            "register",
            {
                "role": "owner",
                "name": "Priya Owner",
                "email": "priya@example.com",
                "phone": "9811111111",
                "password": PASSWORD,
            },
        )
        owner = signed_in(
            APIClient(), self.auth("login", {"email": "priya@example.com", "password": PASSWORD})["access"]
        )
        self.assertEqual(owner.get("/api/v1/owner/library/").status_code, 409)  # no library yet

        library = unwrap(owner.post("/api/v1/owner/library/", LIBRARY_PAYLOAD, format="json"), 201)
        self.assertFalse(library["is_published"])
        plan = unwrap(
            owner.post(
                "/api/v1/owner/library/plans/",
                {"name": "Monthly", "duration_days": 30, "price": "1200.00", "timing_note": ""},
                format="json",
            ),
            201,
        )
        seats = unwrap(
            owner.post("/api/v1/owner/seats/", {"mode": "grid", "rows": ["A"], "seats_per_row": 3}, format="json"), 201
        )
        self.assertEqual(len(seats["created"]), 3)
        library = unwrap(owner.get("/api/v1/owner/library/"), 200)
        self.assertTrue(library["is_published"], "the library goes live by itself once it has a plan and a seat")

        # --- A student finds it, holds a seat and pays ---------------------------------------------------
        self.auth(
            "register",
            {
                "role": "student",
                "name": "Asha Verma",
                "email": "asha@example.com",
                "phone": "9822222222",
                "password": PASSWORD,
            },
        )
        student = signed_in(
            APIClient(), self.auth("login", {"email": "asha@example.com", "password": PASSWORD})["access"]
        )
        public = APIClient()
        listing = unwrap(public.get("/api/v1/libraries/"), 200)
        self.assertEqual([item["id"] for item in listing["items"]], [library["id"]])
        seat_map = unwrap(public.get(f"/api/v1/libraries/{library['id']}/seats/"), 200)
        self.assertEqual(seat_map["counts"], {"total": 3, "empty": 3, "reserved": 0, "occupied": 0})
        seat = seat_map["seats"][0]
        self.assertNotIn("student", json.dumps(seat_map))  # the public map never shows who sits where

        hold = unwrap(
            student.post("/api/v1/student/holds/", {"seat_id": seat["id"], "plan_id": plan["id"]}, format="json"), 201
        )
        self.assertEqual(hold["amount"], "1200.00")
        self.assertEqual(unwrap(public.get(f"/api/v1/libraries/{library['id']}/seats/"))["counts"]["reserved"], 1)

        order = unwrap(
            student.post("/api/v1/payments/orders/", {"hold_id": hold["id"], "amount": "1.00"}, format="json"), 201
        )
        self.assertEqual(order["amount_paise"], 120000)  # the client's amount was ignored

        # The checkout callback alone confirms nothing; the signed gateway event does.
        forged = student.post(
            "/api/v1/payments/verify/",
            {"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_1", "razorpay_signature": "0" * 64},
            format="json",
        )
        self.assertEqual(forged.status_code, 400)
        self.assertEqual(unwrap(student.get("/api/v1/student/memberships/")), [])
        raw = json.dumps(captured_event(order["order_id"], "pay_1", 120000)).encode()
        webhook = APIClient().post(
            "/api/v1/payments/webhook/razorpay/",
            raw,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=self.gateway.webhook_signature(raw),
            HTTP_X_RAZORPAY_EVENT_ID="evt_journey_1",
        )
        self.assertEqual(webhook.status_code, 200)
        verified = unwrap(
            student.post(
                "/api/v1/payments/verify/",
                {
                    "razorpay_order_id": order["order_id"],
                    "razorpay_payment_id": "pay_1",
                    "razorpay_signature": self.gateway.checkout_signature(order["order_id"], "pay_1"),
                },
                format="json",
            ),
            200,
        )  # arriving second, the checkout call is a harmless repeat
        self.assertEqual(verified["payment"]["status"], "success")

        memberships = unwrap(student.get("/api/v1/student/memberships/"))
        self.assertEqual([m["status"] for m in memberships], ["active"])
        membership_id = memberships[0]["id"]
        receipt = unwrap(student.get(f"/api/v1/student/payments/{verified['payment']['id']}/"))
        self.assertEqual(receipt["receipt_number"], verified["payment"]["receipt_number"])
        self.assertEqual(unwrap(public.get(f"/api/v1/libraries/{library['id']}/seats/"))["counts"]["occupied"], 1)

        # --- The student uses the library -------------------------------------------------------------------
        checked_in = unwrap(
            student.post("/api/v1/student/attendance/check-in/", {"library_id": library["id"]}, format="json"), 201
        )
        self.assertEqual(checked_in["status"], "open")
        live = unwrap(owner.get("/api/v1/owner/attendance/live/"))
        self.assertEqual([row["student"]["name"] for row in live], ["Asha Verma"])
        self.assertEqual(
            student.post(
                "/api/v1/student/attendance/check-in/", {"library_id": library["id"]}, format="json"
            ).status_code,
            409,
        )
        unwrap(student.post("/api/v1/student/attendance/check-out/"), 200)
        complaint = unwrap(
            student.post(
                "/api/v1/student/complaints/",
                {"library_id": library["id"], "category": "wifi", "description": "The Wi-Fi drops every evening."},
                format="json",
            ),
            201,
        )
        unwrap(
            student.post(
                "/api/v1/student/visits/",
                {
                    "library_id": library["id"],
                    "preferred_date": str(business_today() + timedelta(days=2)),
                    "preferred_slot": "evening",
                },
                format="json",
            ),
            201,
        )

        # --- The owner sees it, answers and admits a walk-in student -------------------------------------
        dashboard = unwrap(owner.get("/api/v1/owner/dashboard/"))
        self.assertEqual(dashboard["seats"]["occupied"], 1)
        self.assertEqual(dashboard["members"]["active"], 1)
        self.assertEqual(
            (dashboard["open_complaints"], dashboard["pending_visits"], dashboard["today"]["check_ins"]), (1, 1, 1)
        )
        self.assertEqual(dashboard["revenue"]["this_month_total"], "1200.00")

        unwrap(
            owner.patch(
                f"/api/v1/owner/complaints/{complaint['id']}/",
                {"status": "resolved", "owner_response": "Router replaced."},
                format="json",
            ),
            200,
        )
        visit_id = unwrap(owner.get("/api/v1/owner/visits/", {"status": "pending"}))["items"][0]["id"]
        unwrap(
            owner.post(
                f"/api/v1/owner/visits/{visit_id}/decision/",
                {"decision": "accept", "owner_note": "See you at 6"},
                format="json",
            ),
            200,
        )

        free_seat = next(s for s in unwrap(owner.get("/api/v1/owner/seats/"))["seats"] if s["status"] == "empty")
        lookup = unwrap(owner.post("/api/v1/owner/admissions/lookup/", {"phone": "9833333333"}, format="json"))
        self.assertEqual(lookup["match"], "none")
        admitted = unwrap(
            owner.post(
                "/api/v1/owner/admissions/",
                {
                    "student": {"name": "Ravi Walkin", "phone": "9833333333"},
                    "seat_id": free_seat["id"],
                    "plan_id": plan["id"],
                    "payment": {"method": "cash"},
                },
                format="json",
            ),
            201,
        )
        self.assertTrue(admitted["student"]["created"])
        self.assertTrue(admitted["student"]["is_offline"])
        # An offline student has no password, so cannot sign in until they claim the account.
        self.assertEqual(
            APIClient()
            .post(
                "/api/v1/auth/login/",
                {"email": "ravi@example.com", "password": PASSWORD},
                format="json",
                HTTP_ORIGIN=settings.FRONTEND_URL,
            )
            .status_code,
            401,
        )

        renewed = unwrap(
            owner.post(
                f"/api/v1/owner/members/{admitted['membership']['membership_id']}/renewals/",
                {"method": "upi_direct"},
                format="json",
            ),
            201,
        )
        self.assertEqual(
            renewed["payment"]["period_start"], admitted["membership"]["next_due_date"]
        )  # continues, not restarts

        # --- Notifications reached the right people, once -------------------------------------------------
        student_notes = unwrap(student.get("/api/v1/notifications/"))["items"]
        titles = {n["title"] for n in student_notes}
        self.assertIn("Your seat is booked", titles)
        self.assertIn("Your complaint was updated", titles)
        self.assertIn("Your visit request was accepted", titles)
        owner_notes = {n["title"] for n in unwrap(owner.get("/api/v1/notifications/"))["items"]}
        self.assertTrue({"Payment received", "New complaint", "New visit request"} <= owner_notes)
        self.assertEqual(unwrap(student.get("/api/v1/notifications/unread-count/"))["count"], len(student_notes))

        # --- Reports and exports agree with the lists ---------------------------------------------------------
        today = str(business_today())
        revenue = unwrap(owner.get("/api/v1/owner/reports/revenue/", {"from": today, "to": today}))
        self.assertEqual((revenue["total"], revenue["count"]), ("3600.00", 3))
        csv_response = owner.get("/api/v1/owner/exports/payments.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(
            len(b"".join(csv_response.streaming_content).decode().strip().splitlines()), 4
        )  # header + 3 payments

        # --- Isolation: another owner and another student see none of this -------------------------------
        self.auth(
            "register",
            {
                "role": "owner",
                "name": "Other Owner",
                "email": "other@example.com",
                "phone": "9844444444",
                "password": PASSWORD,
            },
        )
        other_owner = signed_in(
            APIClient(), self.auth("login", {"email": "other@example.com", "password": PASSWORD})["access"]
        )
        self.assertEqual(
            other_owner.get(f"/api/v1/owner/members/{membership_id}/").status_code, 409
        )  # no library of their own yet
        other_student = signed_in(
            APIClient(), self.auth("login", {"email": "asha@example.com", "password": PASSWORD})["access"]
        )
        stranger = make_student()
        stranger_client = APIClient()
        stranger_client.force_authenticate(stranger)
        self.assertEqual(stranger_client.get(f"/api/v1/student/memberships/{membership_id}/").status_code, 404)
        self.assertEqual(stranger_client.get(f"/api/v1/student/payments/{verified['payment']['id']}/").status_code, 404)
        self.assertEqual(stranger_client.get("/api/v1/owner/dashboard/").status_code, 403)
        self.assertEqual(other_student.get("/api/v1/owner/members/").status_code, 403)

        # --- The owner ends a membership: the seat is free again and history stays --------------------------
        unwrap(
            owner.post(
                f"/api/v1/owner/members/{membership_id}/archive/", {"reason": "Moved to another city"}, format="json"
            ),
            200,
        )
        self.assertEqual(
            unwrap(public.get(f"/api/v1/libraries/{library['id']}/seats/"))["counts"]["occupied"], 1
        )  # only Ravi remains
        past = unwrap(student.get("/api/v1/student/memberships/", {"include_archived": "true"}))
        self.assertEqual([m["status"] for m in past], ["archived"])
        self.assertEqual(len(unwrap(student.get(f"/api/v1/student/memberships/{membership_id}/"))["payments"]), 1)
