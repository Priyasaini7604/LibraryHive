"""Owner seat manager endpoints #30-#32, #35-#37 and the student booking-hold endpoints #38-#40.

Not here yet, by design: #16 (public seat map) and the status, occupant, hold
and counts fields of #30 need the derived seat status (SPEC.md 4.1); #33 and #34
need its in-use guard. See IMPLEMENTATION_PLAN.md T10.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.mixins import OwnerLibraryScopedMixin, StudentOwnedScopedMixin
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import created, ok

from . import selectors, services
from .models import Seat, SeatHold
from .serializers import (
    CreateHoldInput,
    OwnerHoldSerializer,
    OwnerSeatSerializer,
    ReasonInput,
    SeatCreateInput,
    SeatUpdateInput,
    StudentHoldSerializer,
)


class _OwnerSeatView(OwnerLibraryScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwner, HasLibrary]
    parser_classes = [JSONParser]
    model = Seat


class OwnerSeatListView(_OwnerSeatView):
    """#30 (inventory part): the owner's seats; #31 add seats."""

    @extend_schema(responses={200: OwnerSeatSerializer(many=True)})
    def get(self, request):
        include_inactive = request.query_params.get("include_inactive", "").lower() in ("1", "true", "yes")
        seats = selectors.library_seats(request.user.library, include_inactive=include_inactive)
        return ok(
            {
                "seats": OwnerSeatSerializer(seats, many=True).data,
                "counts": {"total": selectors.active_seat_count(request.user.library)},
            }
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
        return created({"created": OwnerSeatSerializer(seats, many=True).data, "skipped": skipped})


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
        return ok(OwnerSeatSerializer(seat).data)


class OwnerSeatEnableView(_OwnerSeatView):
    """#35 end maintenance."""

    @extend_schema(request=None, responses={200: OwnerSeatSerializer})
    def post(self, request, seat_id):
        seat = self.get_scoped_object(pk=seat_id)
        seat = services.enable_seat(library=request.user.library, seat=seat, actor=request.user)
        return ok(OwnerSeatSerializer(seat).data)


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
