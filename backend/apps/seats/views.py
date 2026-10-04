from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction

from apps.core.permissions import IsOwner, IsLibraryOwnerOf
from apps.libraries.models import Library
from .models import Seat
from .serializers import SeatSerializer, SeatBulkCreateSerializer


class LibrarySeatsView(generics.GenericAPIView):
    """
    GET: List all seats for a given library (Public / authenticated).
    POST: Bulk or single seat addition during setup / management (Owner of library only).
    """
    serializer_class = SeatSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsOwner(), IsLibraryOwnerOf()]
        return [permissions.AllowAny()]

    def get_library(self):
        library_id = self.kwargs.get("library_id")
        library = get_object_or_404(Library, id=library_id)
        if self.request.method == "POST":
            self.check_object_permissions(self.request, library)
        return library

    def get(self, request, library_id):
        library = get_object_or_404(Library, id=library_id)
        seats = Seat.objects.filter(library=library).order_by("label")
        serializer = SeatSerializer(seats, many=True)
        return Response({
            "success": True,
            "data": serializer.data,
            "error": None,
        })

    def post(self, request, library_id):
        library = self.get_library()

        # Support array payload directly: [{"label": "..."}, ...]
        data = request.data
        seats_to_create = []

        if isinstance(data, list):
            for item in data:
                label = item.get("label")
                seat_status = item.get("status", "empty")
                if label:
                    seats_to_create.append(Seat(library=library, label=label, status=seat_status))
        elif isinstance(data, dict):
            # Check if grid layout was provided: { "rows": ["A", "B"], "seats_per_row": 5 }
            if "rows" in data and "seats_per_row" in data:
                rows = data.get("rows", [])
                seats_per_row = int(data.get("seats_per_row", 0))
                for row in rows:
                    for s in range(1, seats_per_row + 1):
                        label = f"Row {row} - Seat {s}"
                        seats_to_create.append(Seat(library=library, label=label, status="empty"))
            elif "seats" in data and isinstance(data["seats"], list):
                for item in data["seats"]:
                    label = item.get("label")
                    seat_status = item.get("status", "empty")
                    if label:
                        seats_to_create.append(Seat(library=library, label=label, status=seat_status))
            elif "label" in data:
                # Single seat
                seats_to_create.append(
                    Seat(library=library, label=data["label"], status=data.get("status", "empty"))
                )

        if not seats_to_create:
            return Response({
                "success": False,
                "data": None,
                "error": "No valid seat data provided.",
            }, status=status.HTTP_400_BAD_REQUEST)

        # Bulk create or update in atomic transaction
        with transaction.atomic():
            created_seats = []
            for seat_obj in seats_to_create:
                seat, _ = Seat.objects.update_or_create(
                    library=library,
                    label=seat_obj.label,
                    defaults={"status": seat_obj.status},
                )
                created_seats.append(seat)

            # Sync total_seats count on library
            total_count = Seat.objects.filter(library=library).count()
            if library.total_seats != total_count:
                library.total_seats = total_count
                library.save(update_fields=["total_seats", "updated_at"])

        serializer = SeatSerializer(created_seats, many=True)
        return Response({
            "success": True,
            "data": serializer.data,
            "error": None,
        }, status=status.HTTP_201_CREATED)


class SeatDetailView(generics.RetrieveUpdateAPIView):
    """
    GET /seats/{id}/: Public inspection of seat details.
    PATCH /seats/{id}/: Owner can manually override seat status or label.
    """
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    lookup_field = "id"

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsOwner(), IsLibraryOwnerOf()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "data": serializer.data,
            "error": None,
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "success": True,
            "data": serializer.data,
            "error": None,
        })
