from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.libraries.models import Library
from apps.seats.models import Seat

User = get_user_model()


class SeatAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Two owners
        self.owner1 = User.objects.create_user(
            email="owner1@example.com",
            name="Owner One",
            password="password123",
            role="owner",
        )
        self.owner2 = User.objects.create_user(
            email="owner2@example.com",
            name="Owner Two",
            password="password123",
            role="owner",
        )

        # Student
        self.student = User.objects.create_user(
            email="student@example.com",
            name="Student One",
            password="password123",
            role="student",
        )

        # Create library for owner1
        self.library1 = Library.objects.create(
            owner=self.owner1,
            name="Apex Library",
            address="Sector 62, Noida",
            latitude=28.6280,
            longitude=77.3649,
            opens_at="07:00:00",
            closes_at="23:00:00",
        )

    def test_owner_can_add_seats_via_grid_layout(self):
        self.client.force_authenticate(user=self.owner1)
        payload = {
            "rows": ["A", "B"],
            "seats_per_row": 3,
        }
        response = self.client.post(
            f"/api/v1/libraries/{self.library1.id}/seats/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        seats = response.data["data"]
        self.assertEqual(len(seats), 6)
        labels = [s["label"] for s in seats]
        self.assertIn("Row A - Seat 1", labels)
        self.assertIn("Row B - Seat 3", labels)

        self.library1.refresh_from_db()
        self.assertEqual(self.library1.total_seats, 6)

    def test_owner_can_add_seats_via_list(self):
        self.client.force_authenticate(user=self.owner1)
        payload = [
            {"label": "Row A - Seat 1", "status": "empty"},
            {"label": "Row A - Seat 2", "status": "empty"},
        ]
        response = self.client.post(
            f"/api/v1/libraries/{self.library1.id}/seats/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["data"]), 2)

    def test_non_owner_cannot_add_seats(self):
        # Authenticate as owner2 and attempt to add seats to owner1's library
        self.client.force_authenticate(user=self.owner2)
        payload = [{"label": "Row X - Seat 1", "status": "empty"}]
        response = self.client.post(
            f"/api/v1/libraries/{self.library1.id}/seats/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as student
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            f"/api/v1/libraries/{self.library1.id}/seats/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_manually_override_seat_status(self):
        seat = Seat.objects.create(
            library=self.library1,
            label="Row A - Seat 1",
            status="empty",
        )

        self.client.force_authenticate(user=self.owner1)
        response = self.client.patch(
            f"/api/v1/seats/{seat.id}/",
            {"status": "occupied"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["status"], "occupied")

        seat.refresh_from_db()
        self.assertEqual(seat.status, "occupied")

    def test_another_owner_cannot_modify_seat(self):
        seat = Seat.objects.create(
            library=self.library1,
            label="Row A - Seat 1",
            status="empty",
        )

        self.client.force_authenticate(user=self.owner2)
        response = self.client.patch(
            f"/api/v1/seats/{seat.id}/",
            {"status": "occupied"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        seat.refresh_from_db()
        self.assertEqual(seat.status, "empty")

    def test_public_can_view_seat_map(self):
        Seat.objects.create(library=self.library1, label="Row A - Seat 1", status="empty")
        Seat.objects.create(library=self.library1, label="Row A - Seat 2", status="occupied")

        # Unauthenticated request
        response = self.client.get(f"/api/v1/libraries/{self.library1.id}/seats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["label"], "Row A - Seat 1")
        self.assertEqual(data[0]["status"], "empty")
        self.assertEqual(data[1]["label"], "Row A - Seat 2")
        self.assertEqual(data[1]["status"], "occupied")
