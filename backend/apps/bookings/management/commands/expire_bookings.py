from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking
from apps.seats.models import Seat


class Command(BaseCommand):
    help = "Expire unpaid reserved bookings and release their seats."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()

        expired_bookings = (
            Booking.objects
            .select_for_update()
            .filter(
                status="reserved",
                reserved_until__lte=now,
            )
        )

        expired_count = 0

        for booking in expired_bookings:
            seat = (
                Seat.objects
                .select_for_update()
                .filter(id=booking.seat_id)
                .first()
            )

            booking.status = "expired"
            booking.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            if seat and seat.status == "reserved":
                seat.status = "empty"
                seat.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

            expired_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Booking expiry completed. "
                f"{expired_count} booking(s) expired."
            )
        )