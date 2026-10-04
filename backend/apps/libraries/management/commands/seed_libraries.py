from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.libraries.models import Library, PricingPlan
from apps.seats.models import Seat

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds sample study libraries with seats and pricing plans for local testing"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding sample libraries, pricing plans, and seats..."))

        # 1. Owner 1: Apex Reading Lounge (Noida Sector 62)
        owner1, _ = User.objects.get_or_create(
            email="owner@example.com",
            defaults={"name": "Rajesh Kumar (Apex)", "role": "owner"},
        )
        owner1.set_password("password123")
        owner1.save()

        lib1, created1 = Library.objects.update_or_create(
            owner=owner1,
            defaults={
                "name": "Apex Reading Lounge & Library",
                "address": "4th Floor, City Hub Complex, Sector 62, Noida, Uttar Pradesh",
                "latitude": 28.6280,
                "longitude": 77.3649,
                "contact_phone": "+91 9876543210",
                "contact_email": "apex@libraryhive.com",
                "total_seats": 24,
                "operating_hours": "07:00 AM - 11:00 PM (7 Days Open)",
                "domains_catered": "UPSC,SSC,NEET,JEE,GATE",
            },
        )

        # Plans for Lib 1
        lib1.plans.all().delete()
        PricingPlan.objects.create(library=lib1, name="Monthly Morning Shift", duration_days=30, price=1200.00)
        PricingPlan.objects.create(library=lib1, name="Monthly Full Day Pass", duration_days=30, price=2200.00)
        PricingPlan.objects.create(library=lib1, name="Quarterly Saver Pass", duration_days=90, price=5800.00)

        # Seats for Lib 1 (Rows A to D, 6 seats each = 24 seats)
        lib1.seats.all().delete()
        seats_to_create_1 = []
        statuses_pattern_1 = ["empty", "empty", "occupied", "empty", "reserved", "empty"]
        for row in ["A", "B", "C", "D"]:
            for num in range(1, 7):
                status = statuses_pattern_1[(num - 1) % len(statuses_pattern_1)]
                seats_to_create_1.append(
                    Seat(library=lib1, label=f"Row {row} - Seat {num}", status=status)
                )
        Seat.objects.bulk_create(seats_to_create_1)
        lib1.total_seats = len(seats_to_create_1)
        lib1.save()

        # 2. Owner 2: Central Hive Study Hall (Connaught Place, Delhi)
        owner2, _ = User.objects.get_or_create(
            email="delhi.owner@example.com",
            defaults={"name": "Anita Sharma (Central Hive)", "role": "owner"},
        )
        owner2.set_password("password123")
        owner2.save()

        lib2, created2 = Library.objects.update_or_create(
            owner=owner2,
            defaults={
                "name": "Central Hive Study Hall",
                "address": "Inner Circle, Connaught Place, New Delhi",
                "latitude": 28.6315,
                "longitude": 77.2167,
                "contact_phone": "+91 9811223344",
                "contact_email": "central@libraryhive.com",
                "total_seats": 20,
                "operating_hours": "06:00 AM - 12:00 Midnight (24/7 during exam season)",
                "domains_catered": "UPSC,CA,Banking,State PSC,CAT",
            },
        )

        lib2.plans.all().delete()
        PricingPlan.objects.create(library=lib2, name="Monthly Standard Pass", duration_days=30, price=1500.00)
        PricingPlan.objects.create(library=lib2, name="Half-Yearly UPSC Sprint", duration_days=180, price=7500.00)

        lib2.seats.all().delete()
        seats_to_create_2 = []
        for row in ["A", "B", "C", "D"]:
            for num in range(1, 6):
                status = "empty" if (row != "B" or num > 2) else "occupied"
                seats_to_create_2.append(
                    Seat(library=lib2, label=f"Row {row} - Seat {num}", status=status)
                )
        Seat.objects.bulk_create(seats_to_create_2)
        lib2.total_seats = len(seats_to_create_2)
        lib2.save()

        # 3. Owner 3: Pragati Self-Study Den (South Extension, Delhi)
        owner3, _ = User.objects.get_or_create(
            email="southex.owner@example.com",
            defaults={"name": "Vikas Verma (Pragati)", "role": "owner"},
        )
        owner3.set_password("password123")
        owner3.save()

        lib3, created3 = Library.objects.update_or_create(
            owner=owner3,
            defaults={
                "name": "Pragati Self-Study Den",
                "address": "South Extension Part II, New Delhi",
                "latitude": 28.5684,
                "longitude": 77.2217,
                "contact_phone": "+91 9711556677",
                "contact_email": "pragati@libraryhive.com",
                "total_seats": 18,
                "operating_hours": "08:00 AM - 10:00 PM (Daily)",
                "domains_catered": "NEET,JEE,General Study,UPSC",
            },
        )

        lib3.plans.all().delete()
        PricingPlan.objects.create(library=lib3, name="Monthly Starter", duration_days=30, price=1100.00)
        PricingPlan.objects.create(library=lib3, name="Quarterly NEET Pack", duration_days=90, price=3000.00)

        lib3.seats.all().delete()
        seats_to_create_3 = []
        for row in ["A", "B", "C"]:
            for num in range(1, 7):
                status = "empty" if num % 3 != 0 else "reserved"
                seats_to_create_3.append(
                    Seat(library=lib3, label=f"Row {row} - Seat {num}", status=status)
                )
        Seat.objects.bulk_create(seats_to_create_3)
        lib3.total_seats = len(seats_to_create_3)
        lib3.save()

        self.stdout.write(self.style.SUCCESS("Successfully seeded 3 libraries with seats and pricing plans:"))
        self.stdout.write(f"  1. {lib1.name} ({lib1.total_seats} seats, Noida Sector 62)")
        self.stdout.write(f"  2. {lib2.name} ({lib2.total_seats} seats, Connaught Place Delhi)")
        self.stdout.write(f"  3. {lib3.name} ({lib3.total_seats} seats, South Extension Delhi)")
