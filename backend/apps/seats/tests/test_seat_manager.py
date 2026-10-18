"""Owner seat manager (#30-#32, #35, SEAT-01/02/09) and tenant isolation."""

import threading

from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.libraries import services as library_services
from apps.libraries.tests.base import make_library, make_plan
from apps.seats import selectors, services
from apps.seats.models import Seat
from apps.seats.services import SeatSpec

SEATS = "/api/v1/owner/seats/"


def client_for(user):
    client = APIClient()
    client.force_authenticate(type(user).objects.get(pk=user.pk))
    return client


class SeatApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.library = make_library()
        self.owner = client_for(self.library.owner)

    def grid(self, rows=("A", "B"), per_row=3, client=None):
        return (client or self.owner).post(
            SEATS, {"mode": "grid", "rows": list(rows), "seats_per_row": per_row}, format="json"
        )

    def labels(self, library=None):
        return list(
            Seat.objects.filter(library=library or self.library, is_active=True)
            .order_by("row_label", "position")
            .values_list("label", flat=True)
        )


class CreateSeatsTests(SeatApiTestCase):
    def test_grid_creates_labelled_seats_with_row_and_position(self):
        response = self.grid()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(len(data["created"]), 6)
        self.assertEqual(data["skipped"], [])
        self.assertEqual(self.labels(), ["A-1", "A-2", "A-3", "B-1", "B-2", "B-3"])
        seat = Seat.objects.get(library=self.library, label="B-2")
        self.assertEqual((seat.row_label, seat.position), ("B", 2))
        self.assertFalse(seat.is_disabled)
        self.assertEqual(
            set(data["created"][0]),
            {"id", "label", "row_label", "position", "is_active", "is_disabled", "disabled_reason"},
        )

    def test_status_is_never_client_writable_or_exposed_before_it_is_derived(self):
        response = self.owner.post(
            SEATS,
            {"mode": "list", "seats": [{"label": "Z-1", "status": "occupied", "is_disabled": True}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        seat = Seat.objects.get(label="Z-1")
        self.assertFalse(seat.is_disabled)
        self.assertNotIn("status", response.json()["data"]["created"][0])

    def test_rerunning_a_grid_skips_existing_seats_and_never_resets_them(self):
        self.grid(per_row=2)
        keep = Seat.objects.get(label="A-1")
        services.update_seat(library=self.library, seat=keep, actor=self.library.owner, data={"position": 9})
        Seat.objects.filter(pk=keep.pk).update(is_disabled=True, disabled_reason="Broken desk")

        response = self.grid(per_row=3)  # A-1, A-2, B-1, B-2 exist; A-3 and B-3 are new
        data = response.json()["data"]
        self.assertEqual(sorted(s["label"] for s in data["created"]), ["A-3", "B-3"])
        self.assertEqual(
            sorted((s["label"], s["reason"]) for s in data["skipped"]),
            [("A-1", "exists"), ("A-2", "exists"), ("B-1", "exists"), ("B-2", "exists")],
        )
        keep.refresh_from_db()
        self.assertEqual((keep.position, keep.is_disabled, keep.disabled_reason), (9, True, "Broken desk"))
        self.assertEqual(Seat.objects.filter(library=self.library).count(), 6)

    def test_list_mode_skips_duplicates_case_insensitively_and_inside_the_request(self):
        self.owner.post(SEATS, {"mode": "list", "seats": [{"label": "Window 1"}]}, format="json")
        response = self.owner.post(
            SEATS,
            {
                "mode": "list",
                "seats": [
                    {"label": "window 1"},
                    {"label": "Desk 2", "row_label": "D", "position": 2},
                    {"label": "DESK 2"},
                ],
            },
            format="json",
        )
        data = response.json()["data"]
        self.assertEqual([s["label"] for s in data["created"]], ["Desk 2"])
        self.assertEqual({s["label"] for s in data["skipped"]}, {"window 1", "DESK 2"})

    def test_removed_seats_free_their_label(self):
        self.grid(rows=("A",), per_row=1)
        Seat.objects.filter(label="A-1").update(is_active=False)
        response = self.grid(rows=("A",), per_row=1)
        self.assertEqual([s["label"] for s in response.json()["data"]["created"]], ["A-1"])
        self.assertEqual(Seat.objects.filter(label="A-1").count(), 2)  # history kept

    def test_validation(self):
        bad = [
            {"mode": "grid"},
            {"mode": "grid", "rows": [], "seats_per_row": 3},
            {"mode": "grid", "rows": ["A"], "seats_per_row": 0},
            {"mode": "grid", "rows": ["A"], "seats_per_row": 51},
            {"mode": "grid", "rows": ["A" * 11], "seats_per_row": 2},
            {"mode": "grid", "rows": [chr(65 + i) for i in range(11)], "seats_per_row": 50},  # 550 seats
            {"mode": "list"},
            {"mode": "list", "seats": [{"label": ""}]},
            {"mode": "list", "seats": [{"label": "x" * 51}]},
            {"mode": "list", "seats": [{"label": f"S{i}"} for i in range(501)]},
            {"mode": "shifts"},
        ]
        for payload in bad:
            response = self.owner.post(SEATS, payload, format="json")
            self.assertEqual(response.status_code, 400, payload if len(str(payload)) < 200 else payload["mode"])
        self.assertFalse(Seat.objects.exists())

    def test_500_seats_in_one_request_is_allowed(self):
        response = self.owner.post(
            SEATS, {"mode": "list", "seats": [{"label": f"S{i}"} for i in range(500)]}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["data"]["created"]), 500)

    def test_creation_is_audited_with_counts_and_library(self):
        self.grid(per_row=2)
        self.grid(per_row=3)
        rows = list(AuditLog.objects.filter(action="seat.create", library=self.library).order_by("created_at"))
        self.assertEqual([r.changes for r in rows], [{"created": 4, "skipped": 0}, {"created": 2, "skipped": 4}])
        self.assertTrue(all(r.actor_id == self.library.owner_id for r in rows))

    def test_first_seat_publishes_a_library_that_has_a_plan(self):
        make_plan(self.library)
        self.library.refresh_from_db()
        self.assertFalse(self.library.is_published)  # no seat yet
        self.grid(rows=("A",), per_row=1)
        self.library.refresh_from_db()
        self.assertTrue(self.library.is_published)

    def test_students_anonymous_and_owners_without_a_library_are_blocked(self):
        payload = {"mode": "grid", "rows": ["A"], "seats_per_row": 1}
        self.assertEqual(APIClient().post(SEATS, payload, format="json").status_code, 401)
        self.assertEqual(client_for(make_student()).post(SEATS, payload, format="json").status_code, 403)
        response = client_for(make_owner()).post(SEATS, payload, format="json")
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "LIBRARY_REQUIRED"))


class ListSeatsTests(SeatApiTestCase):
    def test_lists_active_seats_in_layout_order_with_a_total(self):
        self.grid(per_row=2)
        Seat.objects.filter(label="A-2").update(is_active=False)
        data = self.owner.get(SEATS).json()["data"]
        self.assertEqual([s["label"] for s in data["seats"]], ["A-1", "B-1", "B-2"])
        self.assertEqual(data["counts"], {"total": 3})

    def test_include_inactive_shows_removed_seats_but_not_in_the_total(self):
        self.grid(rows=("A",), per_row=2)
        Seat.objects.filter(label="A-2").update(is_active=False)
        data = self.owner.get(SEATS, {"include_inactive": "true"}).json()["data"]
        self.assertEqual({s["label"]: s["is_active"] for s in data["seats"]}, {"A-1": True, "A-2": False})
        self.assertEqual(data["counts"]["total"], 1)

    def test_public_and_student_cannot_list(self):
        self.assertEqual(APIClient().get(SEATS).status_code, 401)
        self.assertEqual(client_for(make_student()).get(SEATS).status_code, 403)


class UpdateSeatTests(SeatApiTestCase):
    def setUp(self):
        super().setUp()
        self.grid(rows=("A",), per_row=2)
        self.seat = Seat.objects.get(label="A-1")

    def url(self, seat=None, suffix=""):
        return f"{SEATS}{(seat or self.seat).pk}/{suffix}"

    def test_relabel_and_reposition_with_audit_diff(self):
        response = self.owner.patch(self.url(), {"label": " Window 1 ", "row_label": "W", "position": 7}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.seat.refresh_from_db()
        self.assertEqual((self.seat.label, self.seat.row_label, self.seat.position), ("Window 1", "W", 7))
        row = AuditLog.objects.get(action="seat.update")
        self.assertEqual(row.changes["label"], ["A-1", "Window 1"])
        self.assertEqual(row.entity_id, self.seat.pk)

    def test_label_clash_with_another_active_seat_is_conflict_but_keeping_your_own_is_fine(self):
        clash = self.owner.patch(self.url(), {"label": "a-2"}, format="json")
        self.assertEqual((clash.status_code, clash.json()["error_code"]), (409, "CONFLICT"))
        same = self.owner.patch(self.url(), {"label": "A-1", "position": 5}, format="json")
        self.assertEqual(same.status_code, 200)
        self.seat.refresh_from_db()
        self.assertEqual(self.seat.position, 5)

    def test_status_fields_are_ignored(self):
        self.owner.patch(self.url(), {"is_active": False, "is_disabled": True, "status": "occupied"}, format="json")
        self.seat.refresh_from_db()
        self.assertTrue(self.seat.is_active)
        self.assertFalse(self.seat.is_disabled)

    def test_validation(self):
        for payload in ({"label": ""}, {"label": "x" * 51}, {"row_label": "R" * 11}, {"position": -1}):
            self.assertEqual(self.owner.patch(self.url(), payload, format="json").status_code, 400, payload)

    def test_enable_clears_maintenance_and_is_idempotent(self):
        Seat.objects.filter(pk=self.seat.pk).update(is_disabled=True, disabled_reason="Broken")
        for _ in range(2):
            response = self.owner.post(self.url(suffix="enable/"))
            self.assertEqual(response.status_code, 200)
        self.seat.refresh_from_db()
        self.assertEqual((self.seat.is_disabled, self.seat.disabled_reason), (False, ""))
        self.assertEqual(AuditLog.objects.filter(action="seat.enable").count(), 1)

    def test_other_librarys_seat_is_404_on_every_object_endpoint(self):
        other = make_library(name="Other Library")
        services.create_seats(library=other, actor=other.owner, specs=[SeatSpec("A-1")])
        theirs = Seat.objects.get(library=other)
        Seat.objects.filter(pk=theirs.pk).update(is_disabled=True, disabled_reason="Broken")
        for response in (
            self.owner.patch(self.url(theirs), {"label": "Mine"}, format="json"),
            self.owner.post(self.url(theirs, "enable/")),
        ):
            self.assertEqual((response.status_code, response.json()["error_code"]), (404, "NOT_FOUND"))
        theirs.refresh_from_db()
        self.assertEqual((theirs.label, theirs.is_disabled), ("A-1", True))
        self.assertEqual({s["label"] for s in self.owner.get(SEATS).json()["data"]["seats"]}, {"A-1", "A-2"})


class ConstraintTests(TestCase):
    def setUp(self):
        self.library = make_library()

    def test_active_labels_are_unique_per_library_case_insensitively(self):
        Seat.objects.create(library=self.library, label="A-1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Seat.objects.create(library=self.library, label="a-1")
        other = make_library(name="Other Library")
        Seat.objects.create(library=other, label="A-1")  # another library may reuse it

    def test_removed_seats_do_not_hold_their_label(self):
        Seat.objects.create(library=self.library, label="A-1", is_active=False)
        Seat.objects.create(library=self.library, label="A-1")
        Seat.objects.create(library=self.library, label="A-1", is_active=False)

    def test_a_removed_seat_cannot_be_disabled(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Seat.objects.create(library=self.library, label="A-1", is_active=False, is_disabled=True)

    def test_library_with_seats_cannot_be_deleted(self):
        from django.db.models import ProtectedError

        Seat.objects.create(library=self.library, label="A-1")
        with self.assertRaises(ProtectedError):
            self.library.delete()

    def test_unfinished_derived_status_is_not_faked(self):
        self.assertEqual(selectors.active_seat_count(self.library), 0)
        self.assertFalse(hasattr(selectors, "seat_counts_by_library"))


class ConcurrentCreateTests(TransactionTestCase):
    """Two requests adding the same grid at once: every label exists exactly once, nothing fails."""

    def test_parallel_grids_never_duplicate_a_seat(self):
        library = make_library(domain_codes=[], amenity_codes=[])
        barrier = threading.Barrier(4)
        results: list[tuple[int, int]] = []

        def worker():
            try:
                barrier.wait(timeout=10)
                created, skipped = services.create_seats(
                    library=library, actor=library.owner, specs=services.grid_specs(["A", "B"], 5)
                )
                results.append((len(created), len(skipped)))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(len(results), 4)
        self.assertEqual(sorted(results), [(0, 10), (0, 10), (0, 10), (10, 0)])
        self.assertEqual(Seat.objects.filter(library=library).count(), 10)
        library_services.refresh_publish_state(library)
