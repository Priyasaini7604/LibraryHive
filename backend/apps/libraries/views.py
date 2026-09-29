import math
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q

from apps.core.permissions import IsOwner, IsLibraryOwnerOf
from .models import Library, PricingPlan
from .serializers import (
    LibrarySerializer,
    LibraryCreateUpdateSerializer,
    PricingPlanSerializer,
)


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points in kilometers.
    """
    R = 6371.0  # Earth radius in kilometers
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class LibraryListCreateView(generics.GenericAPIView):
    """
    GET /libraries/: Public list and search of libraries.
    POST /libraries/: Owner creates library profile (one-time onboarding).
    """
    queryset = Library.objects.all().select_related("owner").prefetch_related("plans")

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsOwner()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LibraryCreateUpdateSerializer
        return LibrarySerializer

    def get(self, request, *args, **kwargs):
        qs = self.get_queryset()

        # Query filters
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(address__icontains=search)
            )

        domain = request.query_params.get("domain")
        if domain:
            qs = qs.filter(domains_catered__icontains=domain)

        # Coordinate-based proximity filter
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        radius = request.query_params.get("radius")  # in kilometers

        libraries_data = []
        serializer = LibrarySerializer(qs, many=True)

        if lat and lng and radius:
            try:
                lat = float(lat)
                lng = float(lng)
                radius = float(radius)
                for lib in serializer.data:
                    lib_lat = lib.get("latitude")
                    lib_lng = lib.get("longitude")
                    if lib_lat is not None and lib_lng is not None:
                        dist = haversine_distance(lat, lng, lib_lat, lib_lng)
                        if dist <= radius:
                            lib_copy = dict(lib)
                            lib_copy["distance_km"] = round(dist, 2)
                            libraries_data.append(lib_copy)
                libraries_data.sort(key=lambda x: x.get("distance_km", 0))
            except (ValueError, TypeError):
                libraries_data = serializer.data
        else:
            libraries_data = serializer.data

        return Response({
            "success": True,
            "data": libraries_data,
            "error": None,
        })

    def post(self, request, *args, **kwargs):
        # Enforce one library per owner
        existing_library = Library.objects.filter(owner=request.user).first()
        if existing_library:
            return Response({
                "success": False,
                "data": None,
                "error": "Library profile already exists for this owner. Use PATCH /libraries/{id}/ to update.",
                "existing_library_id": str(existing_library.id),
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = LibraryCreateUpdateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        library = serializer.save()

        # Return full representation
        response_serializer = LibrarySerializer(library)
        return Response({
            "success": True,
            "data": response_serializer.data,
            "error": None,
        }, status=status.HTTP_201_CREATED)


class LibraryDetailView(generics.GenericAPIView):
    """
    GET /libraries/{id}/: Public explore page.
    PATCH/PUT /libraries/{id}/: Owner edit library profile.
    """
    queryset = Library.objects.all().select_related("owner").prefetch_related("plans")
    lookup_field = "id"

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsOwner(), IsLibraryOwnerOf()]

    def get(self, request, id):
        library = get_object_or_404(Library, id=id)
        serializer = LibrarySerializer(library)
        return Response({
            "success": True,
            "data": serializer.data,
            "error": None,
        })

    def patch(self, request, id):
        library = get_object_or_404(Library, id=id)
        self.check_object_permissions(request, library)

        serializer = LibraryCreateUpdateSerializer(
            library,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated_library = serializer.save()

        response_serializer = LibrarySerializer(updated_library)
        return Response({
            "success": True,
            "data": response_serializer.data,
            "error": None,
        })

    def put(self, request, id):
        return self.patch(request, id)


class OwnerLibraryMeView(generics.GenericAPIView):
    """
    GET /libraries/me/: Return the authenticated owner's library profile.
    Used for setup checking and profile management.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request):
        library = Library.objects.filter(owner=request.user).first()
        if not library:
            return Response({
                "success": False,
                "data": None,
                "error": "No library profile found for this owner.",
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = LibrarySerializer(library)
        return Response({
            "success": True,
            "data": serializer.data,
            "error": None,
        })
