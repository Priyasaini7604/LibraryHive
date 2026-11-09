"""Direct UPI payments with manual owner approval: settings, QR, requests, approval, races (UPI-01 to UPI-12)."""

import io
import threading
from datetime import timedelta
from urllib.parse import urlparse

import qrcode
import zxingcpp
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.core.exceptions import AppError
from apps.core.models import AuditLog
from apps.core.storage import private_storage
from apps.core.tests.factories import make_owner, make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications.models import Notification
from apps.payments import upi_services
from apps.payments.models import LibraryPaymentSettings, Payment, UpiPaymentRequest
from apps.seats import services as seat_services
from apps.seats.models import SeatHold

from .base import PaymentTestCase, bookable_library, client_for

BASE = "/api/v1"
QR_TEXT = "upi://pay?pa=reading.room@okbank&pn=Reading%20Room&cu=INR"


def qr_image(*, box_size=10, mode="RGB") -> Image.Image:
    code = qrcode.QRCode(border=4, box_size=box_size, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(QR_TEXT)
    return code.make_image(fill_color="black", back_color="white").get_image().convert(mode)


def image_file(image: Image.Image, *, fmt="PNG", name="qr.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


def scans_as_qr(image: Image.Image) -> bool:
    return any(result.text == QR_TEXT for result in zxingcpp.read_barcodes(image.convert("RGB")))


class UpiTestCase(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.library.owner
        self.owner_api = client_for(self.owner)
        self.student_api = client_for(self.student)
        self._utr = 123456789000

    def next_utr(self) -> str:
        self._utr += 1
        return str(self._utr)

    def enable_upi(self, *, with_qr=True):
        response = self.owner_api.patch(
            f"{BASE}/owner/payment-settings/",
            {"upi_id": "reading.room@okbank", "instructions": "Pay the exact amount.", "upi_enabled": True},
            format="json",
        )
        assert response.status_code == 200, response.content
        if with_qr:
            upload = self.owner_api.post(f"{BASE}/owner/payment-settings/qr/", {"image": image_file(qr_image())})
            assert upload.status_code == 200, upload.content

    def fresh_hold(self, student=None):
        """A booking hold for `student` on the first seat that nobody holds or occupies."""
        for seat in self.seats:
            taken = (
                SeatHold.objects.live().filter(seat=seat).exists()
                or Membership.objects.filter(seat=seat, state="active").exists()
            )
            if not taken:
                return self.hold_seat(student, seat=seat)
        raise AssertionError("no free seat left in the fixture")

    def submit(self, *, student=None, hold=None, utr=None, api=None, **extra):
        hold = hold or self.fresh_hold(student)
        payload = {"hold_id": str(hold.pk), "utr": utr or self.next_utr(), **extra}
        return (api or client_for(student or self.student)).post(
            f"{BASE}/student/upi-payments/", payload, format="multipart"
        )

    def submitted(self, **kwargs) -> UpiPaymentRequest:
        response = self.submit(**kwargs)
        assert response.status_code == 201, response.content
        return UpiPaymentRequest.objects.get(pk=response.json()["data"]["id"])

    def approve(self, request, *, api=None, **body):
        return (api or self.owner_api).post(f"{BASE}/owner/upi-payments/{request.pk}/approve/", body, format="json")

    def reject(self, request, reason="Not received", *, api=None):
        return (api or self.owner_api).post(
            f"{BASE}/owner/upi-payments/{request.pk}/reject/", {"reason": reason}, format="json"
        )


class PaymentSettingsTests(UpiTestCase):
    def test_owner_saves_upi_id_and_instructions_and_turns_it_on(self):
        self.enable_upi(with_qr=False)
        row = LibraryPaymentSettings.objects.get(library=self.library)
        self.assertTrue(row.upi_enabled)
        self.assertEqual(row.upi_id, "reading.room@okbank")
        self.assertTrue(AuditLog.objects.filter(action="payment_settings.update", library=self.library).exists())

    def test_cannot_turn_on_without_a_qr_or_a_upi_id(self):
        response = self.owner_api.patch(f"{BASE}/owner/payment-settings/", {"upi_enabled": True}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LibraryPaymentSettings.objects.filter(upi_enabled=True).exists())

    def test_a_malformed_upi_id_is_rejected(self):
        response = self.owner_api.patch(f"{BASE}/owner/payment-settings/", {"upi_id": "not a upi id"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_students_and_anonymous_users_cannot_manage_settings(self):
        self.assertEqual(self.student_api.get(f"{BASE}/owner/payment-settings/").status_code, 403)
        self.assertEqual(self.student_api.patch(f"{BASE}/owner/payment-settings/", {}, format="json").status_code, 403)
        self.assertEqual(APIClient().get(f"{BASE}/owner/payment-settings/").status_code, 401)

    def test_each_owner_only_ever_touches_their_own_library(self):
        other_library, _, _ = bookable_library(owner=make_owner(), domain_codes=[], amenity_codes=[])
        client_for(other_library.owner).patch(
            f"{BASE}/owner/payment-settings/", {"upi_id": "other@okbank", "upi_enabled": True}, format="json"
        )
        self.owner_api.patch(f"{BASE}/owner/payment-settings/", {"upi_id": "mine@okbank"}, format="json")
        self.assertEqual(LibraryPaymentSettings.objects.get(library=other_library).upi_id, "other@okbank")
        self.assertEqual(LibraryPaymentSettings.objects.get(library=self.library).upi_id, "mine@okbank")


class QrUploadTests(UpiTestCase):
    def upload(self, file):
        return self.owner_api.post(f"{BASE}/owner/payment-settings/qr/", {"image": file})

    def served(self, response) -> Image.Image:
        """Fetch the image the way a browser would: from the signed link in the response, without logging in."""
        url = response.json()["data"]["qr_url"]
        fetched = APIClient().get(urlparse(url).path)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched["Content-Type"], "image/webp")
        self.assertIn("no-store", fetched["Cache-Control"])
        return Image.open(io.BytesIO(b"".join(fetched.streaming_content)))

    def test_the_uploaded_qr_is_stored_privately_and_still_scans_when_served(self):
        response = self.upload(image_file(qr_image()))
        self.assertEqual(response.status_code, 200, response.content)
        row = LibraryPaymentSettings.objects.get(library=self.library)
        self.assertTrue(row.qr_key.startswith(f"payments/{self.library.pk}/qr/"))
        self.assertTrue(private_storage().exists(row.qr_key))
        self.assertTrue(scans_as_qr(self.served(response)))

    def test_a_photo_sized_jpeg_qr_still_scans_after_processing(self):
        big = qr_image(box_size=60)  # a few thousand pixels, larger than the 1920 px display size
        self.assertGreater(big.width, 1920)
        response = self.upload(image_file(big, fmt="JPEG", name="qr.jpg"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(scans_as_qr(self.served(response)))

    def test_a_transparent_qr_is_flattened_onto_white_and_still_scans(self):
        transparent = qr_image(mode="RGBA")
        pixels = transparent.load()
        for x in range(transparent.width):
            for y in range(transparent.height):
                if pixels[x, y][:3] == (255, 255, 255):
                    pixels[x, y] = (255, 255, 255, 0)
        response = self.upload(image_file(transparent))
        served = self.served(response)
        self.assertEqual(served.mode, "RGB")
        self.assertTrue(scans_as_qr(served))

    def test_replacing_removes_the_old_object_and_removing_deletes_it(self):
        first = self.upload(image_file(qr_image())).json()["data"]
        old_key = LibraryPaymentSettings.objects.get().qr_key
        self.assertTrue(first["has_qr"])
        self.upload(image_file(qr_image(box_size=12)))
        new_key = LibraryPaymentSettings.objects.get().qr_key
        self.assertNotEqual(old_key, new_key)
        self.assertFalse(private_storage().exists(old_key))
        removed = self.owner_api.delete(f"{BASE}/owner/payment-settings/qr/")
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(removed.json()["data"]["has_qr"])
        self.assertFalse(private_storage().exists(new_key))
        actions = set(AuditLog.objects.filter(library=self.library).values_list("action", flat=True))
        self.assertTrue(
            {"payment_settings.qr_upload", "payment_settings.qr_replace", "payment_settings.qr_remove"} <= actions
        )

    def test_the_qr_cannot_be_removed_while_it_is_the_only_way_to_pay(self):
        self.owner_api.patch(f"{BASE}/owner/payment-settings/", {"upi_id": "", "upi_enabled": False}, format="json")
        self.upload(image_file(qr_image()))
        self.owner_api.patch(f"{BASE}/owner/payment-settings/", {"upi_enabled": True}, format="json")
        response = self.owner_api.delete(f"{BASE}/owner/payment-settings/qr/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.error_code(response), "QR_REQUIRED")

    def test_a_file_that_is_not_an_image_is_refused_whatever_its_name(self):
        fake = SimpleUploadedFile("qr.png", b"<script>alert(1)</script>", content_type="image/png")
        response = self.upload(fake)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.error_code(response), "FILE_TYPE")
        self.assertFalse(LibraryPaymentSettings.objects.filter(library=self.library).exclude(qr_key="").exists())

    def test_an_image_over_the_size_limit_is_refused(self):
        with self.settings(MAX_UPLOAD_BYTES=1000):
            response = self.upload(image_file(qr_image(box_size=20)))
        self.assertEqual(response.status_code, 413)

    def test_a_forged_or_expired_link_serves_nothing(self):
        self.upload(image_file(qr_image()))
        self.assertEqual(APIClient().get("/api/v1/files/private/not-a-real-token/").status_code, 404)
        url = self.owner_api.get(f"{BASE}/owner/payment-settings/").json()["data"]["qr_url"]
        with self.settings(SECRET_KEY="a-different-secret-key-" + "x" * 40):
            self.assertEqual(APIClient().get(urlparse(url).path).status_code, 404)


class PaymentInfoTests(UpiTestCase):
    def test_only_a_student_who_is_paying_this_library_sees_its_qr(self):
        self.enable_upi()
        url = f"{BASE}/student/libraries/{self.library.pk}/upi-info/"
        self.assertEqual(self.student_api.get(url).status_code, 404)  # just browsing
        self.hold_seat()
        response = self.student_api.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["upi_id"], "reading.room@okbank")
        self.assertTrue(data["qr_url"])
        self.assertNotIn("reviewed_by", str(data))
        other = make_student()
        self.assertEqual(client_for(other).get(url).status_code, 404)  # another student has no hold here

    def test_a_hold_at_one_library_does_not_unlock_another_librarys_qr(self):
        other_library, _, _ = bookable_library(owner=make_owner(), domain_codes=[], amenity_codes=[])
        client_for(other_library.owner).patch(
            f"{BASE}/owner/payment-settings/", {"upi_id": "other@okbank", "upi_enabled": True}, format="json"
        )
        self.enable_upi()
        self.hold_seat()  # a hold at self.library only
        self.assertEqual(
            self.student_api.get(f"{BASE}/student/libraries/{other_library.pk}/upi-info/").status_code, 404
        )

    def test_nothing_is_shown_when_the_owner_has_turned_upi_off(self):
        self.enable_upi()
        self.hold_seat()
        self.owner_api.patch(f"{BASE}/owner/payment-settings/", {"upi_enabled": False}, format="json")
        self.assertEqual(self.student_api.get(f"{BASE}/student/libraries/{self.library.pk}/upi-info/").status_code, 404)

    def test_the_checkout_hold_says_whether_upi_is_offered(self):
        self.hold_seat()
        holds = self.student_api.get(f"{BASE}/student/holds/current/")
        self.assertEqual(holds.status_code, 200, holds.content)
        self.assertFalse(holds.json()["data"][0]["library"]["upi_enabled"])
        self.enable_upi()
        holds = self.student_api.get(f"{BASE}/student/holds/current/")
        self.assertTrue(holds.json()["data"][0]["library"]["upi_enabled"])


class SubmitRequestTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()

    def test_a_request_is_created_pending_with_server_side_amount_and_plan(self):
        cheap = self.library.plans.create(name="Cheap", duration_days=7, price="1.00")
        hold = self.hold_seat()
        response = self.student_api.post(
            f"{BASE}/student/upi-payments/",
            {
                "hold_id": str(hold.pk),
                "utr": "  utr 4000 1234 5678  ",
                # None of these is accepted: the server reads them from the hold.
                "amount": "1.00",
                "plan_id": str(cheap.pk),
                "library_id": "00000000-0000-0000-0000-000000000000",
                "status": "approved",
                "student_id": "00000000-0000-0000-0000-000000000000",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["amount"], "1200.00")
        self.assertEqual(data["plan"]["id"], str(self.plan.pk))
        self.assertEqual(data["utr"], "UTR400012345678")
        self.assertEqual(data["library"]["id"], str(self.library.pk))
        request = UpiPaymentRequest.objects.get()
        self.assertEqual(request.student, self.student)
        self.assertEqual(request.seat, self.seat)
        # A claim is not money: nothing was activated and the ledger is untouched.
        self.assertFalse(Membership.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_the_owner_is_told_and_the_submission_is_audited(self):
        request = self.submitted()
        note = Notification.objects.get(recipient=self.owner, type="upi_payment_submitted")
        self.assertEqual(note.entity_id, request.pk)
        self.assertTrue(AuditLog.objects.filter(action="upi_payment.submit", entity_id=request.pk).exists())

    def test_the_seat_is_not_held_longer_by_a_request(self):
        hold = self.hold_seat()
        before = SeatHold.objects.get(pk=hold.pk).expires_at
        self.submitted(hold=hold)
        self.assertEqual(SeatHold.objects.get(pk=hold.pk).expires_at, before)

    def test_utr_must_look_like_a_reference(self):
        for bad in ("123", "", "has-dashes-1234567", "x" * 40):
            response = self.submit(utr=bad) if bad else self.submit(utr=" ")
            self.assertEqual(response.status_code, 400, bad)
            self.student_api = client_for(self.student)
            SeatHold.objects.filter(student=self.student).update(status="cancelled")

    def test_send_exactly_one_of_hold_or_membership(self):
        response = self.student_api.post(f"{BASE}/student/upi-payments/", {"utr": "123456789012"}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_duplicate_utr_is_refused_however_it_is_typed(self):
        self.submitted(utr="ABC123456789")
        other = make_student()
        for variant in ("abc123456789", " abc 123 456 789 ", "ABC123456789"):
            response = self.submit(student=other, utr=variant)
            self.assertEqual(response.status_code, 409, variant)
            self.assertEqual(self.error_code(response), "DUPLICATE_UTR")
            SeatHold.objects.filter(student=other).update(status="cancelled")
        self.assertEqual(UpiPaymentRequest.objects.count(), 1)

    def test_a_rejected_or_cancelled_utr_can_be_sent_again(self):
        first = self.submitted(utr="REUSE0000001")
        self.reject(first)
        seat_services.cancel_hold(student=self.student, hold=first.hold)
        again = self.submit(utr="REUSE0000001")  # the same student may retry; others may not (see test_upi_policy)
        self.assertEqual(again.status_code, 201, again.content)

    def test_a_student_cannot_have_two_pending_requests_at_one_library(self):
        first = self.submitted()
        seat_services.cancel_hold(student=self.student, hold=first.hold)
        second_hold = self.hold_seat(seat=self.seats[1])
        response = self.submit(hold=second_hold)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.error_code(response), "UPI_REQUEST_PENDING")
        self.assertEqual(UpiPaymentRequest.objects.count(), 1)

    def test_the_database_itself_refuses_a_second_pending_request(self):
        first = self.submitted()
        with self.assertRaises(Exception) as caught:
            UpiPaymentRequest.objects.create(
                library=self.library,
                student=self.student,
                plan=self.plan,
                purpose="new_membership",
                hold=first.hold,
                seat=first.seat,
                amount="1200.00",
                utr="DIFFERENT0001",
            )
        self.assertIn("upireq_one_pending_per_student", str(caught.exception))

    def test_another_students_hold_cannot_be_used(self):
        other_hold = self.hold_seat(student=make_student(), seat=self.seats[1])
        response = self.submit(hold=other_hold)  # sent by self.student
        self.assertEqual(response.status_code, 404)

    def test_refused_when_the_library_does_not_take_upi(self):
        self.owner_api.patch(f"{BASE}/owner/payment-settings/", {"upi_enabled": False}, format="json")
        response = self.submit()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.error_code(response), "UPI_DISABLED")

    def test_refused_for_a_plan_that_is_no_longer_offered(self):
        hold = self.hold_seat()
        self.plan.is_active = False
        self.plan.save()
        response = self.submit(hold=hold)
        self.assertEqual(self.error_code(response), "PLAN_INACTIVE")

    def test_a_hold_that_just_lapsed_can_still_report_a_payment(self):
        hold = self.hold_seat()
        self.expire(hold)
        self.assertEqual(self.submit(hold=hold).status_code, 201)

    def test_a_cancelled_hold_cannot(self):
        hold = self.hold_seat()
        seat_services.cancel_hold(student=self.student, hold=hold)
        self.assertEqual(self.error_code(self.submit(hold=hold)), "HOLD_CLOSED")

    def test_a_current_member_cannot_book_again(self):
        hold = self.hold_seat()
        make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seats[2])
        self.assertEqual(self.error_code(self.submit(hold=hold)), "ALREADY_MEMBER")

    def test_anonymous_users_and_owners_cannot_submit(self):
        hold = self.hold_seat()
        payload = {"hold_id": str(hold.pk), "utr": self.next_utr()}
        self.assertEqual(
            APIClient().post(f"{BASE}/student/upi-payments/", payload, format="multipart").status_code, 401
        )
        self.assertEqual(
            self.owner_api.post(f"{BASE}/student/upi-payments/", payload, format="multipart").status_code, 403
        )


class ScreenshotTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()

    def shot(self):
        return image_file(Image.new("RGB", (600, 900), "white"), name="shot.png")

    def test_the_screenshot_is_optional(self):
        request = self.submitted()
        self.assertEqual(request.screenshot_key, "")
        self.assertFalse(
            self.student_api.get(f"{BASE}/student/upi-payments/{request.pk}/").json()["data"]["has_screenshot"]
        )
        self.assertEqual(self.student_api.get(f"{BASE}/student/upi-payments/{request.pk}/screenshot/").status_code, 404)

    def test_a_screenshot_is_private_to_the_student_and_the_owner_of_that_library(self):
        request = self.submitted(screenshot=self.shot())
        self.assertTrue(request.screenshot_key.startswith(f"payments/{self.library.pk}/screenshots/"))
        self.assertTrue(private_storage().exists(request.screenshot_key))

        own = self.student_api.get(f"{BASE}/student/upi-payments/{request.pk}/screenshot/")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(APIClient().get(urlparse(own.json()["data"]["url"]).path).status_code, 200)
        by_owner = self.owner_api.get(f"{BASE}/owner/upi-payments/{request.pk}/screenshot/")
        self.assertEqual(by_owner.status_code, 200)

        other_student = client_for(make_student())
        self.assertEqual(other_student.get(f"{BASE}/student/upi-payments/{request.pk}/screenshot/").status_code, 404)
        other_library, _, _ = bookable_library(owner=make_owner(), domain_codes=[], amenity_codes=[])
        other_owner = client_for(other_library.owner)
        self.assertEqual(other_owner.get(f"{BASE}/owner/upi-payments/{request.pk}/screenshot/").status_code, 404)
        self.assertEqual(self.student_api.get(f"{BASE}/owner/upi-payments/{request.pk}/screenshot/").status_code, 403)

    def test_a_bad_screenshot_creates_no_request_and_leaves_no_file(self):
        before = set(private_storage().listdir(f"payments/{self.library.pk}")[0])
        bad = SimpleUploadedFile("shot.png", b"not an image", content_type="image/png")
        response = self.submit(screenshot=bad)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UpiPaymentRequest.objects.exists())
        self.assertEqual(set(private_storage().listdir(f"payments/{self.library.pk}")[0]), before)

    def test_a_failed_submission_removes_the_screenshot_it_stored(self):
        self.submitted(utr="SHOT00000001")
        other = make_student()
        response = self.submit(student=other, utr="SHOT00000001", screenshot=self.shot())
        self.assertEqual(self.error_code(response), "DUPLICATE_UTR")
        folder = f"payments/{self.library.pk}/screenshots"
        stored = private_storage().listdir(folder)[1] if private_storage().exists(folder) else []
        self.assertEqual(stored, [])


class CancelTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()

    def test_the_student_can_cancel_a_pending_request_once(self):
        request = self.submitted(utr="CANCEL000001")
        response = self.student_api.post(f"{BASE}/student/upi-payments/{request.pk}/cancel/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "cancelled")
        again = self.student_api.post(f"{BASE}/student/upi-payments/{request.pk}/cancel/", {}, format="json")
        self.assertEqual(self.error_code(again), "ALREADY_DECIDED")

    def test_nobody_else_can_cancel_it_and_a_cancelled_request_cannot_be_approved(self):
        request = self.submitted(utr="CANCEL000002")
        intruder = client_for(make_student())
        self.assertEqual(
            intruder.post(f"{BASE}/student/upi-payments/{request.pk}/cancel/", {}, format="json").status_code, 404
        )
        self.student_api.post(f"{BASE}/student/upi-payments/{request.pk}/cancel/", {}, format="json")
        self.assertEqual(self.error_code(self.approve(request)), "ALREADY_DECIDED")
        self.assertFalse(Membership.objects.exists())


class OwnerReviewTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()
        self.other_library, _, _ = bookable_library(owner=make_owner(), domain_codes=[], amenity_codes=[])
        self.other_owner = client_for(self.other_library.owner)

    def test_each_owner_sees_only_their_own_librarys_requests(self):
        request = self.submitted()
        listed = self.owner_api.get(f"{BASE}/owner/upi-payments/").json()["data"]
        self.assertEqual([item["id"] for item in listed["items"]], [str(request.pk)])
        item = listed["items"][0]
        self.assertEqual(item["student"]["name"], self.student.name)
        self.assertEqual(self.owner_api.get(f"{BASE}/owner/upi-payments/summary/").json()["data"]["pending"], 1)
        self.assertEqual(self.other_owner.get(f"{BASE}/owner/upi-payments/").json()["data"]["items"], [])
        self.assertEqual(self.other_owner.get(f"{BASE}/owner/upi-payments/{request.pk}/").status_code, 404)
        self.assertEqual(self.approve(request, api=self.other_owner).status_code, 404)
        self.assertEqual(self.reject(request, api=self.other_owner).status_code, 404)
        self.assertEqual(UpiPaymentRequest.objects.get().status, "pending")

    def test_status_filter(self):
        request = self.submitted()
        self.reject(request)
        self.assertEqual(
            len(self.owner_api.get(f"{BASE}/owner/upi-payments/?status=pending").json()["data"]["items"]), 0
        )
        self.assertEqual(
            len(self.owner_api.get(f"{BASE}/owner/upi-payments/?status=rejected").json()["data"]["items"]), 1
        )

    def test_students_and_anonymous_users_cannot_review(self):
        request = self.submitted()
        self.assertEqual(self.approve(request, api=self.student_api).status_code, 403)
        self.assertEqual(self.reject(request, api=self.student_api).status_code, 403)
        self.assertEqual(self.student_api.get(f"{BASE}/owner/upi-payments/").status_code, 403)
        self.assertEqual(self.approve(request, api=APIClient()).status_code, 401)
        self.assertFalse(Membership.objects.exists())


class ApprovalTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()

    def test_approving_activates_the_membership_and_writes_the_ledger_row(self):
        request = self.submitted()
        response = self.approve(request)
        self.assertEqual(response.status_code, 200, response.content)
        request.refresh_from_db()
        membership = Membership.objects.get()
        self.assertEqual((membership.student, membership.seat, membership.plan), (self.student, self.seat, self.plan))
        self.assertEqual(membership.state, "active")
        self.assertEqual(membership.source, "online")
        self.assertEqual(membership.next_due_date - membership.start_date, timedelta(days=30))

        payment = Payment.objects.get()
        self.assertEqual(
            (payment.status, payment.method, payment.channel, payment.verified_via, payment.purpose),
            ("success", "upi_direct", "offline", "manual", "new_membership"),
        )
        self.assertEqual(
            (payment.amount, payment.recorded_by, payment.membership), (self.plan.price, self.owner, membership)
        )
        self.assertTrue(payment.receipt_number.startswith("LH-"))
        self.assertIn(request.utr, payment.notes)
        self.assertEqual((payment.period_start, payment.period_end), (membership.start_date, membership.next_due_date))

        self.assertEqual((request.status, request.reviewed_by, request.payment), ("approved", self.owner, payment))
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(SeatHold.objects.get(student=self.student).status, "completed")

    def test_student_notification_and_audit_trail(self):
        request = self.submitted()
        self.approve(request)
        note = Notification.objects.get(recipient=self.student, type="upi_payment_approved")
        self.assertIn(self.seat.label, note.body)
        audit = AuditLog.objects.get(action="upi_payment.approve", entity_id=request.pk)
        self.assertEqual(audit.actor, self.owner)
        self.assertEqual(audit.library, self.library)
        self.assertTrue(AuditLog.objects.filter(action="membership.create", library=self.library).exists())

    def test_the_student_sees_the_decision(self):
        request = self.submitted()
        self.approve(request)
        data = self.student_api.get(f"{BASE}/student/upi-payments/{request.pk}/").json()["data"]
        self.assertEqual(data["status"], "approved")
        self.assertTrue(data["receipt_number"])
        self.assertFalse(data["can_cancel"])

    def test_approving_twice_changes_nothing_the_second_time(self):
        request = self.submitted()
        self.assertEqual(self.approve(request).status_code, 200)
        second = self.approve(request)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(self.error_code(second), "ALREADY_DECIDED")
        self.assertEqual((Membership.objects.count(), Payment.objects.count()), (1, 1))

    def test_approve_then_reject_and_reject_then_approve_are_both_refused(self):
        first = self.submitted()
        self.approve(first)
        self.assertEqual(self.error_code(self.reject(first)), "ALREADY_DECIDED")
        other = make_student()
        second = self.submitted(student=other, hold=self.hold_seat(student=other, seat=self.seats[1]))
        self.reject(second)
        self.assertEqual(self.error_code(self.approve(second)), "ALREADY_DECIDED")
        self.assertEqual((Membership.objects.count(), Payment.objects.count()), (1, 1))

    def test_an_expired_hold_is_fine_if_the_seat_is_still_free(self):
        hold = self.hold_seat()
        request = self.submitted(hold=hold)
        self.expire(hold)
        self.assertEqual(self.approve(request).status_code, 200)
        self.assertEqual(Membership.objects.get().seat, self.seat)

    def test_the_client_cannot_steer_the_amount_or_the_student(self):
        request = self.submitted()
        response = self.approve(request, amount="1.00", student_id=str(make_student().pk), plan_id=str(self.plan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.get().amount, self.plan.price)
        self.assertEqual(Membership.objects.get().student, self.student)


class RejectionTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()

    def test_rejecting_activates_nothing_and_tells_the_student_why(self):
        request = self.submitted()
        response = self.reject(request, "No credit of 1200 in my account")
        self.assertEqual(response.status_code, 200, response.content)
        request.refresh_from_db()
        self.assertEqual((request.status, request.reviewed_by), ("rejected", self.owner))
        self.assertIsNotNone(request.reviewed_at)
        self.assertFalse(Membership.objects.exists())
        self.assertFalse(Payment.objects.exists())
        note = Notification.objects.get(recipient=self.student, type="upi_payment_rejected")
        self.assertIn("No credit of 1200", note.body)
        self.assertIn("does not refund", note.body)  # never implies an automatic refund
        self.assertTrue(AuditLog.objects.filter(action="upi_payment.reject", entity_id=request.pk).exists())
        shown = self.student_api.get(f"{BASE}/student/upi-payments/{request.pk}/").json()["data"]
        self.assertEqual((shown["status"], shown["review_note"]), ("rejected", "No credit of 1200 in my account"))
        self.assertEqual(shown["library"]["id"], str(self.library.pk))  # how to contact the owner

    def test_a_reason_is_required(self):
        request = self.submitted()
        self.assertEqual(self.reject(request, "").status_code, 400)
        self.assertEqual(self.reject(request, "  ").status_code, 400)
        self.assertEqual(UpiPaymentRequest.objects.get().status, "pending")


class SeatUnavailableTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()

    def test_a_seat_taken_before_approval_blocks_activation_and_changes_nothing(self):
        request = self.submitted()
        self.expire(request.hold)
        make_membership(library=self.library, plan=self.plan, student=make_student(), seat=self.seat)
        response = self.approve(request)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.error_code(response), "SEAT_UNAVAILABLE")
        self.assertIn("another free seat", response.json()["error"])
        self.assertIn("refund", response.json()["error"])
        request.refresh_from_db()
        self.assertEqual(request.status, "pending")
        self.assertEqual(Membership.objects.count(), 1)  # only the other student's
        self.assertFalse(Payment.objects.exists())

    def test_another_students_live_hold_on_the_seat_also_blocks(self):
        request = self.submitted()
        self.expire(request.hold)
        self.hold_seat(student=make_student())  # a fresh live hold on the same seat
        self.assertEqual(self.error_code(self.approve(request)), "SEAT_UNAVAILABLE")

    def test_a_disabled_seat_blocks(self):
        request = self.submitted()
        self.expire(request.hold)
        seat_services.disable_seat(library=self.library, seat=self.seat, actor=self.owner, reason="Broken desk")
        self.assertEqual(self.error_code(self.approve(request)), "SEAT_UNAVAILABLE")

    def test_the_owner_can_approve_onto_another_free_seat(self):
        request = self.submitted()
        self.expire(request.hold)
        make_membership(library=self.library, plan=self.plan, student=make_student(), seat=self.seat)
        response = self.approve(request, seat_id=str(self.seats[1].pk))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Membership.objects.get(student=self.student).seat, self.seats[1])
        self.assertTrue(AuditLog.objects.get(action="upi_payment.approve").changes["alternative_seat"])
        self.assertEqual(Payment.objects.count(), 1)

    def test_an_alternative_seat_must_be_free_and_in_this_library(self):
        request = self.submitted()
        self.expire(request.hold)
        make_membership(library=self.library, plan=self.plan, student=make_student(), seat=self.seat)
        make_membership(library=self.library, plan=self.plan, student=make_student(), seat=self.seats[1])
        self.assertEqual(self.error_code(self.approve(request, seat_id=str(self.seats[1].pk))), "SEAT_UNAVAILABLE")
        _, _, other_seats = bookable_library(owner=make_owner(), domain_codes=[], amenity_codes=[])
        self.assertEqual(self.approve(request, seat_id=str(other_seats[0].pk)).status_code, 404)
        self.assertEqual(UpiPaymentRequest.objects.get().status, "pending")
        self.assertFalse(Payment.objects.exists())

    def test_the_student_cannot_be_activated_if_they_already_became_a_member(self):
        request = self.submitted()
        make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seats[2])
        self.assertEqual(self.error_code(self.approve(request)), "ALREADY_MEMBER")
        self.assertFalse(Payment.objects.exists())


class RenewalTests(UpiTestCase):
    def setUp(self):
        super().setUp()
        self.enable_upi()
        self.membership = make_membership(
            library=self.library, plan=self.plan, student=self.student, seat=self.seat, due_in=3
        )

    def submit_renewal(self, utr=None, **extra):
        return self.student_api.post(
            f"{BASE}/student/upi-payments/",
            {"membership_id": str(self.membership.pk), "utr": utr or self.next_utr(), **extra},
            format="multipart",
        )

    def test_approval_extends_the_same_membership_and_never_creates_another(self):
        due = self.membership.next_due_date
        response = self.submit_renewal()
        self.assertEqual(response.status_code, 201, response.content)
        request = UpiPaymentRequest.objects.get()
        self.assertEqual(request.purpose, "renewal")
        self.assertEqual(self.membership.next_due_date, due)  # a claim extends nothing
        self.assertEqual(self.approve(request).status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.next_due_date, due + timedelta(days=30))
        self.assertEqual(Membership.objects.count(), 1)
        payment = Payment.objects.get()
        self.assertEqual((payment.purpose, payment.method, payment.status), ("renewal", "upi_direct", "success"))
        self.assertEqual((payment.period_start, payment.period_end), (due, due + timedelta(days=30)))
        self.assertEqual(self.approve(request).status_code, 409)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.next_due_date, due + timedelta(days=30))  # no double extension

    def test_renewal_opens_only_near_the_due_date(self):
        Membership.objects.filter(pk=self.membership.pk).update(next_due_date=timezone.localdate() + timedelta(days=20))
        response = self.submit_renewal()
        self.assertEqual(self.error_code(response), "RENEWAL_NOT_OPEN")

    def test_a_membership_that_ended_meanwhile_cannot_be_renewed(self):
        self.submit_renewal()
        request = UpiPaymentRequest.objects.get()
        Membership.objects.filter(pk=self.membership.pk).update(
            state="archived", archived_at=timezone.now(), archived_by=self.owner
        )
        response = self.approve(request)
        self.assertEqual(self.error_code(response), "MEMBERSHIP_ARCHIVED")
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(UpiPaymentRequest.objects.get().status, "pending")

    def test_someone_elses_membership_cannot_be_renewed(self):
        intruder = client_for(make_student())
        response = intruder.post(
            f"{BASE}/student/upi-payments/",
            {"membership_id": str(self.membership.pk), "utr": self.next_utr()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)


class ExistingPaymentsUnaffectedTests(UpiTestCase):
    def test_the_reconcile_job_never_touches_upi_requests(self):
        from apps.payments import services

        self.enable_upi()
        request = self.submitted()
        UpiPaymentRequest.objects.filter(pk=request.pk).update(created_at=timezone.now() - timedelta(days=2))
        counts = services.reconcile_stale_orders()
        self.assertEqual(counts["checked"], 0)
        self.assertEqual(UpiPaymentRequest.objects.get().status, "pending")

    def test_the_online_checkout_still_works_when_a_library_also_offers_upi(self):
        self.enable_upi()
        hold = self.hold_seat()
        order = self.order_for(hold)
        self.assertEqual(self.paid(order["order_id"]).status_code, 200)
        self.assertEqual(Membership.objects.get().student, self.student)
        self.assertEqual(Payment.objects.get().method, "gateway")


class UpiRaceTests(TransactionTestCase):
    """Two things happening at once: exactly one wins and the books stay consistent."""

    def setUp(self):
        self.library, self.plan, self.seats = bookable_library(domain_codes=[], amenity_codes=[])
        self.owner = self.library.owner
        upi_services.update_settings(
            library=self.library, actor=self.owner, data={"upi_id": "race@okbank", "upi_enabled": True}
        )

    def hold_and_submit(self, seat, utr):
        student = make_student()
        hold = seat_services.create_booking_hold(student=student, seat_id=seat.pk, plan_id=self.plan.pk)
        return upi_services.submit_request(student=student, hold_id=hold.pk, utr=utr)

    def race(self, jobs):
        barrier = threading.Barrier(len(jobs))
        outcomes: list[str] = []

        def worker(job):
            try:
                barrier.wait(timeout=15)
                job()
                outcomes.append("ok")
            except AppError as exc:
                outcomes.append(exc.code)
            except Exception as exc:  # a database error here is a failure of the guard under test
                outcomes.append(f"ERROR {type(exc).__name__}")
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(job,)) for job in jobs]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        return sorted(outcomes)

    def test_two_simultaneous_approvals_activate_once(self):
        request = self.hold_and_submit(self.seats[0], "RACE00000001")
        approve = lambda: upi_services.approve_request(library=self.library, owner=self.owner, request_id=request.pk)  # noqa: E731
        outcomes = self.race([approve, approve, approve])
        self.assertEqual(outcomes, ["ALREADY_DECIDED", "ALREADY_DECIDED", "ok"])
        self.assertEqual((Membership.objects.count(), Payment.objects.count()), (1, 1))
        self.assertEqual(UpiPaymentRequest.objects.get().status, "approved")

    def test_approve_and_reject_at_the_same_moment_give_one_decision(self):
        request = self.hold_and_submit(self.seats[0], "RACE00000002")
        outcomes = self.race(
            [
                lambda: upi_services.approve_request(library=self.library, owner=self.owner, request_id=request.pk),
                lambda: upi_services.reject_request(
                    library=self.library, owner=self.owner, request_id=request.pk, reason="Not received"
                ),
            ]
        )
        self.assertEqual(outcomes, ["ALREADY_DECIDED", "ok"])
        request.refresh_from_db()
        if request.status == "approved":
            self.assertEqual((Membership.objects.count(), Payment.objects.count()), (1, 1))
        else:
            self.assertEqual((request.status, Membership.objects.count(), Payment.objects.count()), ("rejected", 0, 0))

    def test_approve_and_student_cancel_at_the_same_moment_give_one_outcome(self):
        request = self.hold_and_submit(self.seats[0], "RACE00000003")
        outcomes = self.race(
            [
                lambda: upi_services.approve_request(library=self.library, owner=self.owner, request_id=request.pk),
                lambda: upi_services.cancel_request(student=request.student, request_id=request.pk),
            ]
        )
        self.assertEqual(outcomes, ["ALREADY_DECIDED", "ok"])
        request.refresh_from_db()
        self.assertEqual(Membership.objects.count(), 1 if request.status == "approved" else 0)

    def test_two_requests_for_one_seat_activate_only_one(self):
        # Two students each paid for the same seat (the holds had lapsed); the owner approves both at once.
        first = self.hold_and_submit(self.seats[0], "RACE00000004")
        SeatHold.objects.filter(pk=first.hold_id).update(expires_at=timezone.now() - timedelta(minutes=1))
        second = self.hold_and_submit(self.seats[0], "RACE00000005")
        SeatHold.objects.filter(pk=second.hold_id).update(expires_at=timezone.now() - timedelta(minutes=1))
        outcomes = self.race(
            [
                lambda: upi_services.approve_request(library=self.library, owner=self.owner, request_id=first.pk),
                lambda: upi_services.approve_request(library=self.library, owner=self.owner, request_id=second.pk),
            ]
        )
        self.assertEqual(outcomes, ["SEAT_UNAVAILABLE", "ok"])
        self.assertEqual((Membership.objects.count(), Payment.objects.count()), (1, 1))
        self.assertEqual(UpiPaymentRequest.objects.filter(status="pending").count(), 1)

    def test_the_same_utr_sent_by_two_students_at_once_is_accepted_once(self):
        students = [make_student(), make_student()]
        holds = [
            seat_services.create_booking_hold(student=student, seat_id=seat.pk, plan_id=self.plan.pk)
            for student, seat in zip(students, self.seats, strict=False)
        ]
        jobs = [
            lambda s=student, h=hold: upi_services.submit_request(student=s, hold_id=h.pk, utr="RACE00000006")
            for student, hold in zip(students, holds, strict=True)
        ]
        self.assertEqual(self.race(jobs), ["DUPLICATE_UTR", "ok"])
        self.assertEqual(UpiPaymentRequest.objects.count(), 1)
