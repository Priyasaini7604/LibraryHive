"""Load clearly labelled demo data: `python manage.py seed_demo` (T26). Never runs in production.

Everything is created through the same services the API uses (registration, library, plans, seats, admission,
renewal, attendance, complaints, visits), so the demo exercises real code paths. Demo accounts use the reserved
`@demo.libraryhive.test` domain and a published password. Running it again changes nothing that already exists.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

DEMO_DOMAIN = "demo.libraryhive.test"
DEMO_PASSWORD = "Demo-pass-12345"  # published on purpose: demo data only
OWNER_EMAIL = f"owner@{DEMO_DOMAIN}"

STUDENTS = [
    # (name, phone, exam, due in days: None = online-style fresh month)
    ("Aarav Mishra", "9876500001", "upsc", 20),
    ("Diya Sharma", "9876500002", "neet", 2),
    ("Kabir Singh", "9876500003", "ssc", -3),
    ("Meera Iyer", "9876500004", "upsc", -9),
    ("Rohan Gupta", "9876500005", "jee", 6),
    ("Sana Khan", "9876500006", "neet", None),
]


class Command(BaseCommand):
    help = "Create a demo owner, library, members, payments, attendance, complaints and visits. Not for production."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true", help="Allow running when DEBUG is off (never in production)."
        )

    def handle(self, *args, force=False, **options):
        if settings.ENVIRONMENT == "production":
            raise CommandError("seed_demo never runs in production.")
        if not settings.DEBUG and not force:
            raise CommandError("seed_demo is for local use. Set DEBUG=True or pass --force on a non-production server.")

        from apps.accounts import services as accounts
        from apps.accounts.models import User
        from apps.attendance import services as attendance
        from apps.complaints import services as complaints
        from apps.libraries import services as libraries
        from apps.libraries.models import Library
        from apps.memberships import services as memberships
        from apps.memberships.models import Membership
        from apps.seats import services as seats
        from apps.seats.models import Seat
        from apps.visits import services as visits

        owner = User.objects.filter(email=OWNER_EMAIL).first()
        if owner is None:
            owner = accounts.register(
                role="owner", name="Demo Owner", email=OWNER_EMAIL, phone="9876500000", password=DEMO_PASSWORD
            ).user
            self.stdout.write(f"Created owner {OWNER_EMAIL}")

        library = Library.objects.filter(owner=owner).first()
        if library is None:
            library = libraries.create_library(
                owner=owner,
                data={
                    "name": "Demo Study Hall",
                    "description": "Demo data for LibraryHive. Not a real library.",
                    "address": "1 Demo Road",
                    "city": "Prayagraj",
                    "area": "Civil Lines",
                    "latitude": Decimal("25.4358"),
                    "longitude": Decimal("81.8463"),
                    "contact_phone": "9876500000",
                    "contact_email": OWNER_EMAIL,
                    "opens_at": "06:00",
                    "closes_at": "22:00",
                    "operating_notes": "Demo",
                    "domain_codes": [],
                    "amenity_codes": [],
                },
            )
        plan = library.plans.filter(name="Monthly").first() or libraries.create_plan(
            library=library, actor=owner, data={"name": "Monthly", "duration_days": 30, "price": Decimal("1200.00")}
        )
        if not library.plans.filter(name="Quarterly").exists():
            libraries.create_plan(
                library=library,
                actor=owner,
                data={"name": "Quarterly", "duration_days": 90, "price": Decimal("3200.00")},
            )
        if not Seat.objects.filter(library=library).exists():
            seats.create_seats(library=library, actor=owner, specs=seats.grid_specs(["A", "B", "C"], 8))
        library.refresh_from_db()

        free = iter(Seat.objects.filter(library=library, is_active=True).order_by("row_label", "position"))
        admitted = 0
        for name, phone, exam, due_in in STUDENTS:
            email = f"{name.split()[0].lower()}@{DEMO_DOMAIN}"
            if User.objects.filter(email=email).exists():
                continue
            student = accounts.register(
                role="student", name=name, email=email, phone=phone, password=DEMO_PASSWORD, domain_code=exam
            ).user
            seat = next(free)
            while Membership.objects.filter(seat=seat, state="active").exists():
                seat = next(free)
            result = memberships.admit_offline_student(
                library=library,
                owner=owner,
                student={"name": name, "phone": phone, "email": email},
                seat_id=seat.pk,
                plan_id=plan.pk,
                start_date=None,
                payment={"method": "cash"},
            )
            if due_in is not None:  # demo only: move the dates so dues, overdue and renewals have something to show
                due = timezone.localdate() + timedelta(days=due_in)
                Membership.objects.filter(pk=result.membership.pk).update(
                    start_date=due - timedelta(days=30), next_due_date=due
                )
            admitted += 1
            if student.name.startswith(("Aarav", "Diya")):
                attendance.owner_check_in(library=library, owner=owner, membership_id=result.membership.pk)

        if admitted:
            aarav = User.objects.get(email=f"aarav@{DEMO_DOMAIN}")
            if not aarav.complaints.exists():
                complaints.create_complaint(
                    student=aarav,
                    library_id=library.pk,
                    category="wifi",
                    description="The Wi-Fi drops every evening around 8 PM.",
                )
            meera = User.objects.get(email=f"meera@{DEMO_DOMAIN}")
            if not meera.visit_requests.exists():
                visits.request_visit(
                    student=meera,
                    library_id=library.pk,
                    preferred_date=timezone.localdate() + timedelta(days=3),
                    preferred_slot="morning",
                )

        self.stdout.write(self.style.SUCCESS(f"Demo data ready ({admitted} new members)."))
        self.stdout.write(f"  Owner:   {OWNER_EMAIL}  /  {DEMO_PASSWORD}")
        self.stdout.write(
            f"  Student: aarav@{DEMO_DOMAIN}  /  {DEMO_PASSWORD}  (more: diya, kabir, meera, rohan, sana)"
        )
        self.stdout.write("  Run `python manage.py run_scheduled_jobs` to create the renewal reminders.")
