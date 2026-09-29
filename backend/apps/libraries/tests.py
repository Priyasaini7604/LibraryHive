from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.libraries.models import Library, PricingPlan
from apps.seats.models import Seat

User = get_user_model()


class LibraryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create two owners
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

        # Create a student
        self.student = User.objects.create_user(
            email="student@example.com",
            name="Student One",
            password="password123",
            role="student",
        )

    def test_owner_can_create_library_with_plans_and_seats(self):
        self.client.force_authenticate(user=self.owner1)
        payload = {
            "name": "Central Hive Library",
            "address": "123 Knowledge Park, Delhi",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "contact_phone": "+919876543210",
            "contact_email": "central@hive.com",
            "opens_at": "08:00:00",
            "closes_at": "22:00:00",
            "operating_hours": "08:00 AM - 10:00 PM",
            "domains_catered": "UPSC,SSC,NEET",
            "pricing_plans": [
                {"name": "Monthly", "duration_days": 30, "price": 1200.00},
                {"name": "Quarterly", "duration_days": 90, "price": 3200.00},
            ],
            "initial_seats": [
                {"label": "Row A - Seat 1", "status": "empty"},
                {"label": "Row A - Seat 2", "status": "empty"},
                {"label": "Row B - Seat 1", "status": "empty"},
            ],
        }

        response = self.client.post("/api/v1/libraries/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(data["name"], "Central Hive Library")
        self.assertEqual(len(data["plans"]), 2)
        self.assertEqual(data["total_seats"], 3)
        self.assertEqual(data["domains"], ["UPSC", "SSC", "NEET"])

        # Check DB
        library = Library.objects.get(owner=self.owner1)
        self.assertEqual(library.plans.count(), 2)
        self.assertEqual(library.seats.count(), 3)
        self.assertEqual(library.seats.filter(status="empty").count(), 3)

    def test_owner_cannot_create_duplicate_library(self):
        self.client.force_authenticate(user=self.owner1)
        payload = {
            "name": "First Library",
            "address": "Address 1",
            "latitude": 28.0,
            "longitude": 77.0,
            "opens_at": "08:00:00",
            "closes_at": "20:00:00",
        }
        res1 = self.client.post("/api/v1/libraries/", payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Attempt to create second library
        res2 = self.client.post("/api/v1/libraries/", payload, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res2.data["success"])
        self.assertIn("already exists", res2.data["error"])

    def test_owner_can_edit_library_profile(self):
        self.client.force_authenticate(user=self.owner1)
        library = Library.objects.create(
            owner=self.owner1,
            name="Original Name",
            address="Original Address",
            latitude=28.0,
            longitude=77.0,
            opens_at="08:00:00",
            closes_at="20:00:00",
        )

        patch_payload = {
            "name": "Updated Name",
            "address": "Updated Address",
            "operating_hours": "24 Hours Open",
        }
        response = self.client.patch(f"/api/v1/libraries/{library.id}/", patch_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["name"], "Updated Name")
        self.assertEqual(response.data["data"]["operating_hours"], "24 Hours Open")

        library.refresh_from_db()
        self.assertEqual(library.name, "Updated Name")

    def test_owner_cannot_edit_another_owners_library(self):
        library1 = Library.objects.create(
            owner=self.owner1,
            name="Owner 1 Library",
            address="Addr 1",
            latitude=28.0,
            longitude=77.0,
            opens_at="08:00:00",
            closes_at="20:00:00",
        )

        # Authenticate as owner2 and attempt to patch owner1's library
        self.client.force_authenticate(user=self.owner2)
        response = self.client.patch(
            f"/api/v1/libraries/{library1.id}/",
            {"name": "Hacked Name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        library1.refresh_from_db()
        self.assertEqual(library1.name, "Owner 1 Library")

    def test_student_cannot_create_or_edit_library(self):
        self.client.force_authenticate(user=self.student)
        payload = {
            "name": "Student Library",
            "address": "Addr",
            "latitude": 28.0,
            "longitude": 77.0,
            "opens_at": "08:00:00",
            "closes_at": "20:00:00",
        }
        res_create = self.client.post("/api/v1/libraries/", payload, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_library_me_endpoint(self):
        self.client.force_authenticate(user=self.owner1)
        # Before creation: returns 404
        res_before = self.client.get("/api/v1/libraries/me/")
        self.assertEqual(res_before.status_code, status.HTTP_404_NOT_FOUND)

        # Create library
        Library.objects.create(
            owner=self.owner1,
            name="Owner 1 Lib",
            address="Addr",
            latitude=28.0,
            longitude=77.0,
            opens_at="08:00:00",
            closes_at="20:00:00",
        )

        res_after = self.client.get("/api/v1/libraries/me/")
        self.assertEqual(res_after.status_code, status.HTTP_200_OK)
        self.assertEqual(res_after.data["data"]["name"], "Owner 1 Lib")

    def test_public_can_list_and_search_libraries(self):
        Library.objects.create(
            owner=self.owner1,
            name="Connaught Place Study Hub",
            address="CP, New Delhi",
            latitude=28.6315,
            longitude=77.2167,
            opens_at="08:00:00",
            closes_at="22:00:00",
            domains_catered="UPSC,JEE",
        )
        Library.objects.create(
            owner=self.owner2,
            name="South Ex Readers Den",
            address="South Extension, New Delhi",
            latitude=28.5684,
            longitude=77.2217,
            opens_at="07:00:00",
            closes_at="23:00:00",
            domains_catered="NEET,CA",
        )

        # Unauthenticated search by domain
        res_domain = self.client.get("/api/v1/libraries/?domain=UPSC")
        self.assertEqual(res_domain.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_domain.data["data"]), 1)
        self.assertEqual(res_domain.data["data"][0]["name"], "Connaught Place Study Hub")

        # Proximity search near Connaught Place (radius 3 km)
        res_prox = self.client.get("/api/v1/libraries/?lat=28.6310&lng=77.2160&radius=3")
        self.assertEqual(res_prox.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_prox.data["data"]), 1)
        self.assertEqual(res_prox.data["data"][0]["name"], "Connaught Place Study Hub")
