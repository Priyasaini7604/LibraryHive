from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.libraries.models import Seat
from apps.memberships.models import Membership

from .models import Payment
from .serializers import PaymentSerializer


class PaymentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(student=request.user)
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PaymentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = serializer.validated_data["booking"]

        if booking.student != request.user:
            return Response(
                {"detail": "You can only pay for your own booking."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.status != "reserved":
            return Response(
                {"detail": "This booking is not available for payment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.reserved_until <= timezone.now():
            return Response(
                {"detail": "This booking has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = serializer.save(
            student=request.user,
            status="pending",
        )

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentSuccessView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, payment_id):

        payment = Payment.objects.select_for_update().select_related(
            "booking",
            "booking__seat",
            "booking__plan",
            "booking__library",
        ).get(
            id=payment_id
        )

        if payment.student != request.user:
            return Response(
                {"detail": "You can only confirm your own payment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if payment.status == "successful":
            return Response(
                {"detail": "Payment is already successful."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = payment.booking

        if booking.status != "reserved":
            return Response(
                {"detail": "This booking is no longer available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.reserved_until <= timezone.now():
            return Response(
                {"detail": "This booking has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        seat = Seat.objects.select_for_update().get(
            id=booking.seat_id
        )

        if seat.status != "reserved":
            return Response(
                {"detail": "Seat is not reserved for this booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.status = "successful"
        payment.transaction_id = f"TEST-{payment.id}"
        payment.paid_at = timezone.now()
        payment.save(
            update_fields=[
                "status",
                "transaction_id",
                "paid_at",
                "updated_at",
            ]
        )

        booking.status = "confirmed"
        booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        seat.status = "occupied"
        seat.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        start_date = timezone.localdate()
        next_due_date = start_date + timezone.timedelta(
            days=booking.plan.duration_days
        )

        membership = Membership.objects.create(
            student=request.user,
            library=booking.library,
            plan=booking.plan,
            seat=booking.seat,
            start_date=start_date,
            next_due_date=next_due_date,
            status="active",
        )

        return Response(
            {
                "message": "Payment successful.",
                "payment": PaymentSerializer(payment).data,
                "booking_status": booking.status,
                "seat_status": seat.status,
                "membership_id": membership.id,
                "membership_status": membership.status,
                "next_due_date": membership.next_due_date,
            },
            status=status.HTTP_200_OK,
        )