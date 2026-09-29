import razorpay

from django.conf import settings
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

        serializer = PaymentSerializer(
            payments,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request):
        serializer = PaymentSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = serializer.validated_data["booking"]

        if booking.student != request.user:
            return Response(
                {
                    "detail": "You can only pay for your own booking."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.status != "reserved":
            return Response(
                {
                    "detail": "This booking is not available for payment."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.reserved_until <= timezone.now():
            return Response(
                {
                    "detail": "This booking has expired."
                },
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


class PaymentOrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        booking_id = request.data.get("booking")

        if not booking_id:
            return Response(
                {
                    "detail": "Booking ID is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            booking = Booking.objects.select_related(
                "plan",
                "library",
            ).get(
                id=booking_id
            )

        except Booking.DoesNotExist:
            return Response(
                {
                    "detail": "Booking not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if booking.student != request.user:
            return Response(
                {
                    "detail": "You can only pay for your own booking."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.status != "reserved":
            return Response(
                {
                    "detail": "This booking is not available for payment."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.reserved_until <= timezone.now():
            return Response(
                {
                    "detail": "This booking has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = booking.plan.price

        # Check whether a pending payment already exists
        existing_payment = Payment.objects.filter(
            booking=booking,
            status="pending",
        ).first()

        if existing_payment:
            return Response(
                {
                    "order_id": existing_payment.razorpay_order_id,
                    "amount": existing_payment.amount,
                    "currency": "INR",
                    "key_id": settings.RAZORPAY_KEY_ID,
                    "booking_id": booking.id,
                    "payment_id": existing_payment.id,
                },
                status=status.HTTP_200_OK,
            )

        # Create Razorpay client
        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
            )
        )

        # Create Razorpay order
        razorpay_order = client.order.create(
            {
                "amount": int(amount * 100),
                "currency": "INR",
                "receipt": str(booking.id),
            }
        )

        # Create local payment record
        payment = Payment.objects.create(
            student=request.user,
            booking=booking,
            amount=amount,
            payment_method="razorpay",
            status="pending",
            razorpay_order_id=razorpay_order["id"],
        )

        return Response(
            {
                "order_id": razorpay_order["id"],
                "amount": payment.amount,
                "currency": "INR",
                "key_id": settings.RAZORPAY_KEY_ID,
                "booking_id": booking.id,
                "payment_id": payment.id,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        razorpay_order_id = request.data.get(
            "razorpay_order_id"
        )

        razorpay_payment_id = request.data.get(
            "razorpay_payment_id"
        )

        razorpay_signature = request.data.get(
            "razorpay_signature"
        )

        if not razorpay_order_id:
            return Response(
                {
                    "detail": "razorpay_order_id is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not razorpay_payment_id:
            return Response(
                {
                    "detail": "razorpay_payment_id is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not razorpay_signature:
            return Response(
                {
                    "detail": "razorpay_signature is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.select_for_update().select_related(
                "booking",
                "booking__seat",
                "booking__plan",
                "booking__library",
            ).get(
                razorpay_order_id=razorpay_order_id
            )

        except Payment.DoesNotExist:
            return Response(
                {
                    "detail": "Payment record not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if payment.student != request.user:
            return Response(
                {
                    "detail": "You can only verify your own payment."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if payment.status == "successful":
            return Response(
                {
                    "detail": "Payment is already successful."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = payment.booking

        if booking.status != "reserved":
            return Response(
                {
                    "detail": "This booking is no longer available."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.reserved_until <= timezone.now():
            return Response(
                {
                    "detail": "This booking has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify Razorpay signature
        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
            )
        )

        try:
            client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature,
                }
            )

        except razorpay.errors.SignatureVerificationError:
            payment.status = "failed"
            payment.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "detail": "Invalid Razorpay payment signature."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lock seat before changing its status
        seat = Seat.objects.select_for_update().get(
            id=booking.seat_id
        )

        if seat.status != "reserved":
            return Response(
                {
                    "detail": "Seat is not reserved for this booking."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark payment successful
        payment.status = "successful"
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.transaction_id = razorpay_payment_id
        payment.paid_at = timezone.now()

        payment.save(
            update_fields=[
                "status",
                "razorpay_payment_id",
                "razorpay_signature",
                "transaction_id",
                "paid_at",
                "updated_at",
            ]
        )

        # Confirm booking
        booking.status = "confirmed"

        booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        # Occupy seat
        seat.status = "occupied"

        seat.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        # Create membership
        start_date = timezone.localdate()

        next_due_date = (
            start_date
            + timezone.timedelta(
                days=booking.plan.duration_days
            )
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
                "message": "Payment verified successfully.",
                "payment": PaymentSerializer(payment).data,
                "booking_status": booking.status,
                "seat_status": seat.status,
                "membership_id": membership.id,
                "membership_status": membership.status,
                "next_due_date": membership.next_due_date,
            },
            status=status.HTTP_200_OK,
        )


class PaymentSuccessView(APIView):
    """
    Temporary test endpoint.

    This endpoint simulates a successful payment.
    Real Razorpay payments should use PaymentVerifyView.
    """

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
                {
                    "detail": "You can only confirm your own payment."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if payment.status == "successful":
            return Response(
                {
                    "detail": "Payment is already successful."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = payment.booking

        if booking.status != "reserved":
            return Response(
                {
                    "detail": "This booking is no longer available."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.reserved_until <= timezone.now():
            return Response(
                {
                    "detail": "This booking has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        seat = Seat.objects.select_for_update().get(
            id=booking.seat_id
        )

        if seat.status != "reserved":
            return Response(
                {
                    "detail": "Seat is not reserved for this booking."
                },
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

        next_due_date = (
            start_date
            + timezone.timedelta(
                days=booking.plan.duration_days
            )
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
                "message": "Test payment successful.",
                "payment": PaymentSerializer(payment).data,
                "booking_status": booking.status,
                "seat_status": seat.status,
                "membership_id": membership.id,
                "membership_status": membership.status,
                "next_due_date": membership.next_due_date,
            },
            status=status.HTTP_200_OK,
        )