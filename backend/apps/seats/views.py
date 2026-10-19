"""Public seat map #16, owner seat manager #30-#37 and the student booking-hold endpoints #38-#40."""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import NotFound
from apps.core.mixins import OwnerLibraryScopedMixin, StudentOwnedScopedMixin
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import created, ok
from apps.libraries import selectors as library_selectors

from . import selectors, services
from .models import Seat, SeatHold
from .serializers import (
    CreateHoldInput,
    OwnerHoldSerializer,
    OwnerSeatSerializer,
    PublicSeatSerializer,
    ReasonInput,
    SeatCreateInput,
    SeatUpdateInput,
    StudentHoldSerializer,
)


class PublicSeatMapView(APIView):
    """#16: the live seat map of a published library. Never reveals who holds or occupies a seat."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: PublicSeatSerializer(many=True)})
    def get(self, request, library_id):
        library = library_selectors.public_library(library_id)
        if library is None:
            raise NotFound()
        data = {
            "seats": PublicSeatSerializer(selectors.seat_map(library), many=True).data,
            "counts": selectors.library_seat_counts(library),
        }
        return ok(data, headers={"Cache-Control": "no-store"})


class _OwnerSeatView(OwnerLibraryScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwner, HasLibrary]
    parser_classes = [JSONParser]
    model = Seat

    def seat_detail(self, seat):
        """The seat as the manager shows it: derived status plus occupant and hold detail."""
        return selectors.owner_seat_map(self.request.user.library, include_inactive=True, seat_ids=[seat.pk])[0]


class OwnerSeatListView(_OwnerSeatView):
    """#30 the seat manager and owner seat map; #31 add seats."""

    @extend_schema(responses={200: OwnerSeatSerializer(many=True)})
    def get(self, request):
        include_inactive = request.query_params.get("include_inactive", "").lower() in ("1", "true", "yes")
        library = request.user.library
        seats = selectors.owner_seat_map(library, include_inactive=include_inactive)
        return ok(
            {"seats": OwnerSeatSerializer(seats, many=True).data, "counts": selectors.library_seat_counts(library)}
        )

    @extend_schema(request=SeatCreateInput, responses={201: None})
    def post(self, request):
        data = SeatCreateInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if values["mode"] == "grid":
            specs = services.grid_specs(values["rows"], values["seats_per_row"])
        else:
            specs = [
                services.SeatSpec(
                    label=item["label"], row_label=item.get("row_label", ""), position=item.get("position")
                )
                for item in values["seats"]
            ]
        seats, skipped = services.create_seats(library=request.user.library, actor=request.user, specs=specs)
        detail = selectors.owner_seat_map(request.user.library, seat_ids=[seat.pk for seat in seats])
        return created({"created": OwnerSeatSerializer(detail, many=True).data, "skipped": skipped})


class OwnerSeatDetailView(_OwnerSeatView):
    """#32 relabel or reposition."""

    @extend_schema(request=SeatUpdateInput, responses={200: OwnerSeatSerializer})
    def patch(self, request, seat_id):
        seat = self.get_scoped_object(pk=seat_id)
        data = SeatUpdateInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        seat = services.update_seat(
            library=request.user.library, seat=seat, actor=request.user, data=data.validated_data
        )
        return ok(OwnerSeatSerializer(self.seat_detail(seat)).data)


class OwnerSeatEnableView(_OwnerSeatView):
    """#35 end maintenance."""

    @extend_schema(request=None, responses={200: OwnerSeatSerializer})
    def post(self, request, seat_id):
        seat = self.get_scoped_object(pk=seat_id)
        seat = services.enable_seat(library=request.user.library, seat=seat, actor=request.user)
        return ok(OwnerSeatSerializer(self.seat_detail(seat)).data)


class OwnerSeatDeactivateView(_OwnerSeatView):
    """#33 remove a seat (soft). Refused while it has a member or a live hold."""

    @extend_schema(request=ReasonInput, responses={200: OwnerSeatSerializer})
    def post(self, request, seat_id):
        seat = self.get_scoped_object(pk=seat_id)
        data = ReasonInput(data=request.data)
        data.is_valid(raise_exception=True)
        seat = services.deactivate_seat(
            library=request.user.library, seat=seat, actor=request.user, reason=data.validated_data["reason"]
        )
        return ok(OwnerSeatSerializer(self.seat_detail(seat)).data)


class OwnerSeatDisableView(_OwnerSeatView):
    """#34 take a seat out of service for maintenance. Same guard as #33."""

    @extend_schema(request=ReasonInput, responses={200: OwnerSeatSerializer})
    def post(self, request, seat_id):
        seat = self.get_scoped_object(pk=seat_id)
        data = ReasonInput(data=request.data)
        data.is_valid(raise_exception=True)
        seat = services.disable_seat(
            library=request.user.library, seat=seat, actor=request.user, reason=data.validated_data["reason"]
        )
        return ok(OwnerSeatSerializer(self.seat_detail(seat)).data)


class OwnerManualHoldView(_OwnerSeatView):
    """#36 block a free seat for an offline or physical reason."""

    @extend_schema(request=ReasonInput, responses={201: OwnerHoldSerializer})
    def post(self, request, seat_id):
        data = ReasonInput(data=request.data)
        data.is_valid(raise_exception=True)
        hold = services.place_manual_hold(
            library=request.user.library, seat_id=seat_id, actor=request.user, reason=data.validated_data["reason"]
        )
        return created(OwnerHoldSerializer(hold).data)


class OwnerHoldReleaseView(OwnerLibraryScopedMixin, APIView):
    """#37 release any pending hold of the owner's library."""

    permission_classes = [IsAuthenticated, IsOwner, HasLibrary]
    parser_classes = [JSONParser]
    model = SeatHold

    @extend_schema(request=ReasonInput, responses={200: OwnerHoldSerializer})
    def post(self, request, hold_id):
        hold = self.get_scoped_object(pk=hold_id)
        data = ReasonInput(data=request.data)
        data.is_valid(raise_exception=True)
        hold = services.release_hold(
            library=request.user.library, hold=hold, actor=request.user, reason=data.validated_data["reason"]
        )
        return ok(OwnerHoldSerializer(hold).data)


class _StudentHoldView(StudentOwnedScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    parser_classes = [JSONParser]
    model = SeatHold


class StudentHoldCreateView(_StudentHoldView):
    """#38 start a booking: hold the seat for the configured window."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hold_create"

    @extend_schema(request=CreateHoldInput, responses={201: StudentHoldSerializer})
    def post(self, request):
        data = CreateHoldInput(data=request.data)
        data.is_valid(raise_exception=True)
        hold = services.create_booking_hold(
            student=request.user, seat_id=data.validated_data["seat_id"], plan_id=data.validated_data["plan_id"]
        )
        return created(StudentHoldSerializer(hold).data)


class StudentCurrentHoldsView(_StudentHoldView):
    """#39 resume an in-progress booking after a page reload (live holds only)."""

    @extend_schema(responses={200: StudentHoldSerializer(many=True)})
    def get(self, request):
        return ok(StudentHoldSerializer(selectors.current_booking_holds(request.user), many=True).data)


class StudentHoldCancelView(_StudentHoldView):
    """#40 abandon a booking."""

    @extend_schema(request=None, responses={200: StudentHoldSerializer})
    def post(self, request, hold_id):
        hold = self.get_scoped_object(pk=hold_id)
        hold = services.cancel_hold(student=request.user, hold=hold)
        return ok(StudentHoldSerializer(hold).data)
