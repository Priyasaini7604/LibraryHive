from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.seats.models import Seat
from .models import Booking
from .serializers import BookingSerializer


class BookingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(student=request.user)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        serializer = BookingSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        seat_id = serializer.validated_data["seat"].id

        seat = Seat.objects.select_for_update().get(id=seat_id)

        if seat.status != "empty":
            return Response(
                {"detail": "This seat is not available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking = serializer.save(
            student=request.user,
            status="reserved",
            reserved_until=timezone.now() + timezone.timedelta(minutes=15),
        )

        seat.status = "reserved"
        seat.save(update_fields=["status", "updated_at"])

        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )


class BookingExpireView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        now = timezone.now()

        expired_bookings = Booking.objects.select_for_update().filter(
            status="reserved",
            reserved_until__lte=now,
        )

        count = 0

        for booking in expired_bookings:
            seat = Seat.objects.select_for_update().get(
                id=booking.seat_id
            )

            booking.status = "expired"
            booking.save(update_fields=["status", "updated_at"])

            if seat.status == "reserved":
                seat.status = "empty"
                seat.save(update_fields=["status", "updated_at"])

            count += 1

        return Response({
            "message": "Expired bookings processed.",
            "expired_count": count,
        })  
    