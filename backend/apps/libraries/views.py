"""Public discovery (#14, #15) and owner library and plan endpoints (#17-#24)."""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import Conflict, NotFound
from apps.core.mixins import OwnerLibraryScopedMixin
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasLibrary, IsOwner
from apps.core.responses import created, ok

from . import selectors, services
from .models import LibraryPhoto, PricingPlan
from .serializers import (
    LibraryInput,
    OwnerLibrarySerializer,
    OwnerPhotoSerializer,
    OwnerPlanSerializer,
    PhotoInput,
    PhotoUploadInput,
    PlanInput,
    PublicLibraryDetailSerializer,
    PublicLibraryListSerializer,
    PublicListQuery,
)


class PublicLibraryListView(APIView):
    """#14: discovery list. Published and active libraries only."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(parameters=[PublicListQuery], responses={200: PublicLibraryListSerializer(many=True)})
    def get(self, request):
        query = PublicListQuery(data=request.query_params.dict() | {"amenity": request.query_params.getlist("amenity")})
        query.is_valid(raise_exception=True)
        params = query.validated_data
        libraries = selectors.public_libraries(
            search=params.get("search") or None,
            domain=params.get("domain") or None,
            amenities=params.get("amenity"),
            lat=params.get("lat"),
            lng=params.get("lng"),
            radius_km=params["radius_km"],
            sort=params.get("sort"),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(libraries, request)
        context = {"seat_counts": selectors.seat_counts_by_library([lib.pk for lib in page])}
        return paginator.get_paginated_response(PublicLibraryListSerializer(page, many=True, context=context).data)


class PublicLibraryDetailView(APIView):
    """#15: explore page. 404 when the library is not published or not active."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: PublicLibraryDetailSerializer})
    def get(self, request, library_id):
        library = selectors.public_library(library_id)
        if library is None:
            raise NotFound()
        return ok(PublicLibraryDetailSerializer(library).data)


class OwnerLibraryView(APIView):
    """#17 create, #18 read with the publish checklist, #19 edit the profile."""

    permission_classes = [IsAuthenticated, IsOwner]
    parser_classes = [JSONParser]

    def _library(self, request):
        library = getattr(request.user, "library", None)
        if library is None:
            raise Conflict("Finish setting up your library first.", code="LIBRARY_REQUIRED")
        return library

    @extend_schema(responses={200: OwnerLibrarySerializer})
    def get(self, request):
        return ok(OwnerLibrarySerializer(self._library(request)).data)

    @extend_schema(request=LibraryInput, responses={201: OwnerLibrarySerializer})
    def post(self, request):
        data = LibraryInput(data=request.data)
        data.is_valid(raise_exception=True)
        library = services.create_library(owner=request.user, data=data.validated_data)
        return created(OwnerLibrarySerializer(library).data)

    @extend_schema(request=LibraryInput, responses={200: OwnerLibrarySerializer})
    def patch(self, request):
        library = self._library(request)
        data = LibraryInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        library = services.update_library(library=library, actor=request.user, data=data.validated_data)
        return ok(OwnerLibrarySerializer(library).data)


class _OwnerPlanView(OwnerLibraryScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwner, HasLibrary]
    parser_classes = [JSONParser]
    model = PricingPlan


class OwnerPlanListView(_OwnerPlanView):
    """#20 all plans including inactive, #21 add a plan."""

    @extend_schema(responses={200: OwnerPlanSerializer(many=True)})
    def get(self, request):
        return ok(OwnerPlanSerializer(self.get_queryset(), many=True).data)

    @extend_schema(request=PlanInput, responses={201: OwnerPlanSerializer})
    def post(self, request):
        data = PlanInput(data=request.data)
        data.is_valid(raise_exception=True)
        plan = services.create_plan(library=request.user.library, actor=request.user, data=data.validated_data)
        return created(OwnerPlanSerializer(plan).data)


class OwnerPlanDetailView(_OwnerPlanView):
    """#22 edit a plan."""

    @extend_schema(request=PlanInput, responses={200: OwnerPlanSerializer})
    def patch(self, request, plan_id):
        plan = self.get_scoped_object(pk=plan_id)
        data = PlanInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        plan = services.update_plan(
            library=request.user.library, plan=plan, actor=request.user, data=data.validated_data
        )
        return ok(OwnerPlanSerializer(plan).data)


class OwnerPlanDeactivateView(_OwnerPlanView):
    """#23 hide a plan from booking."""

    @extend_schema(request=None, responses={200: OwnerPlanSerializer})
    def post(self, request, plan_id):
        plan = self.get_scoped_object(pk=plan_id)
        plan = services.deactivate_plan(library=request.user.library, plan=plan, actor=request.user)
        return ok(OwnerPlanSerializer(plan).data)


class OwnerPlanActivateView(_OwnerPlanView):
    """#24 re-enable a plan."""

    @extend_schema(request=None, responses={200: OwnerPlanSerializer})
    def post(self, request, plan_id):
        plan = self.get_scoped_object(pk=plan_id)
        plan = services.activate_plan(library=request.user.library, plan=plan, actor=request.user)
        return ok(OwnerPlanSerializer(plan).data)


class _OwnerPhotoView(OwnerLibraryScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwner, HasLibrary]
    model = LibraryPhoto


class OwnerPhotoListView(_OwnerPhotoView):
    """#25 gallery management, #26 upload (multipart, verified and re-encoded)."""

    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "upload"

    def get_throttles(self):
        # Only uploads use the stricter `upload` bucket; listing the gallery is a plain read.
        return [ScopedRateThrottle()] if self.request.method == "POST" else super().get_throttles()

    @extend_schema(responses={200: OwnerPhotoSerializer(many=True)})
    def get(self, request):
        return ok(OwnerPhotoSerializer(self.get_queryset(), many=True).data)

    @extend_schema(request={"multipart/form-data": PhotoUploadInput}, responses={201: OwnerPhotoSerializer})
    def post(self, request):
        data = PhotoUploadInput(data=request.data)
        data.is_valid(raise_exception=True)
        photo = services.upload_photo(
            library=request.user.library,
            actor=request.user,
            uploaded_file=data.validated_data["image"],
            caption=data.validated_data.get("caption", ""),
        )
        return created(OwnerPhotoSerializer(photo).data)


class OwnerPhotoDetailView(_OwnerPhotoView):
    """#27 caption and order, #29 delete."""

    parser_classes = [JSONParser]

    @extend_schema(request=PhotoInput, responses={200: OwnerPhotoSerializer})
    def patch(self, request, photo_id):
        photo = self.get_scoped_object(pk=photo_id)
        data = PhotoInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        photo = services.update_photo(
            library=request.user.library, photo=photo, actor=request.user, data=data.validated_data
        )
        return ok(OwnerPhotoSerializer(photo).data)

    @extend_schema(responses={200: None})
    def delete(self, request, photo_id):
        photo = self.get_scoped_object(pk=photo_id)
        services.delete_photo(library=request.user.library, photo=photo, actor=request.user)
        return ok({})


class OwnerPhotoSetCoverView(_OwnerPhotoView):
    """#28 choose the cover."""

    parser_classes = [JSONParser]

    @extend_schema(request=None, responses={200: OwnerPhotoSerializer})
    def post(self, request, photo_id):
        photo = self.get_scoped_object(pk=photo_id)
        photo = services.set_cover(library=request.user.library, photo=photo, actor=request.user)
        return ok(OwnerPhotoSerializer(photo).data)
