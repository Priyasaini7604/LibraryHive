from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.memberships.models import Membership
from apps.notifications.models import Notification


class Command(BaseCommand):
    help = "Generate membership renewal and overdue notifications."

    def handle(self, *args, **options):
        today = timezone.localdate()
        upcoming_date = today + timedelta(days=3)

        memberships = (
            Membership.objects
            .filter(status__in=["active", "due", "overdue"])
            .select_related(
                "student",
                "library",
                "library__owner",
            )
        )

        created_count = 0

        for membership in memberships:
            due_date = membership.next_due_date

            if not due_date:
                continue

            # -------------------------------------------------
            # Determine notification type
            # -------------------------------------------------
            if today <= due_date <= upcoming_date:
                notification_type = "renewal_upcoming"

                student_title = "Membership Renewal Upcoming"
                student_message = (
                    f"Your membership at {membership.library.name} "
                    f"is due on {due_date}."
                )

                owner_title = "Member Renewal Upcoming"
                owner_message = (
                    f"The membership of {membership.student.email} "
                    f"at {membership.library.name} "
                    f"is due on {due_date}."
                )

                if membership.status == "active":
                    membership.status = "due"
                    membership.save(
                        update_fields=["status", "updated_at"]
                    )

            elif due_date < today:
                notification_type = "payment_overdue"

                student_title = "Membership Payment Overdue"
                student_message = (
                    f"Your membership at {membership.library.name} "
                    f"was due on {due_date} and is now overdue."
                )

                owner_title = "Member Payment Overdue"
                owner_message = (
                    f"The membership of {membership.student.email} "
                    f"at {membership.library.name} "
                    f"was due on {due_date} and is now overdue."
                )

                if membership.status != "overdue":
                    membership.status = "overdue"
                    membership.save(
                        update_fields=["status", "updated_at"]
                    )

            else:
                continue

            # -------------------------------------------------
            # Student notification
            # -------------------------------------------------
            student_exists = Notification.objects.filter(
                recipient=membership.student,
                membership=membership,
                notification_type=notification_type,
            ).exists()

            if not student_exists:
                Notification.objects.create(
                    recipient=membership.student,
                    library=membership.library,
                    membership=membership,
                    notification_type=notification_type,
                    title=student_title,
                    message=student_message,
                )

                created_count += 1

            # -------------------------------------------------
            # Owner notification
            # -------------------------------------------------
            owner = membership.library.owner

            if owner:
                owner_exists = Notification.objects.filter(
                    recipient=owner,
                    membership=membership,
                    notification_type=notification_type,
                ).exists()

                if not owner_exists:
                    Notification.objects.create(
                        recipient=owner,
                        library=membership.library,
                        membership=membership,
                        notification_type=notification_type,
                        title=owner_title,
                        message=owner_message,
                    )

                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Notification generation completed. "
                f"{created_count} notification(s) created."
            )
        )