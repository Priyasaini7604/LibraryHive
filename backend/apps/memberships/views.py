"""Membership endpoints #48-#54, #56, #57 (BACKEND_ARCHITECTURE.md 9.8)."""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance import selectors as attendance_selectors
from apps.complaints import selectors as complaint_selectors
from apps.core.exceptions import NotFound
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import created, ok
from apps.payments import selectors as payment_selectors

from . import selectors, serializers, services

OWNER = [IsAuthenticated, IsOwner, HasLibrary]


def _paginate(request, queryset, row):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([row(item) for item in page])


def _annotated(membership):
    """Re-read a membership with its derived status after a write."""
    return selectors.owner_member(membership.library, membership.pk)


class OwnerRenewalView(APIView):
    """#48: record an offline renewal payment."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.RenewalInput, responses={201: None})
    def post(self, request, membership_id):
        data = serializers.RenewalInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        result = services.renew_offline(
            library=request.user.library,
            owner=request.user,
            membership_id=membership_id,
            method=values["method"],
            plan_id=values.get("plan_id"),
            paid_at=values.get("paid_at"),
            notes=values.get("notes", ""),
        )
        return created(
            {
                "payment": serializers.payment_row(result.payment),
                "membership": serializers.member_row(_annotated(result.membership)),
            }
        )


class OwnerDuesView(APIView):
    """#49: due and overdue members, most overdue first."""

    permission_classes = OWNER

    @extend_schema(parameters=[serializers.DuesQuery], responses={200: None})
    def get(self, request):
        query = serializers.DuesQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.owner_dues(request.user.library, **query.validated_data)
        return _paginate(request, queryset, serializers.due_row)


class OwnerMemberListView(APIView):
    """#50: the unified member directory."""

    permission_classes = OWNER

    @extend_schema(operation_id="owner_members_list", parameters=[serializers.MemberQuery], responses={200: None})
    def get(self, request):
        query = serializers.MemberQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.owner_members(request.user.library, **query.validated_data)
        return _paginate(request, queryset, serializers.member_row)


class OwnerMemberDetailView(APIView):
    """#51: one member with their period history and other tenures here."""

    permission_classes = OWNER

    @extend_schema(responses={200: None})
    def get(self, request, membership_id):
        membership = selectors.owner_member(request.user.library, membership_id)
        if membership is None:
            raise NotFound()
        payments = payment_selectors.membership_payments(membership)
        others = selectors.other_memberships_here(membership)
        return ok(
            serializers.member_detail(
                membership,
                payments,
                others,
                attendance_summary=attendance_selectors.member_summary(membership.library, membership.student),
                complaints_count=complaint_selectors.count_for_member(membership.library, membership.student),
            )
        )


class OwnerArchiveView(APIView):
    """#52: archive a membership and free the seat."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.ArchiveInput, responses={200: None})
    def post(self, request, membership_id):
        data = serializers.ArchiveInput(data=request.data)
        data.is_valid(raise_exception=True)
        membership = services.archive_membership(
            library=request.user.library,
            owner=request.user,
            membership_id=membership_id,
            reason=data.validated_data["reason"],
        )
        return ok(serializers.member_row(_annotated(membership)))


class AdmissionLookupView(APIView):
    """#53: pre-check an identity before admitting a walk-in student."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.LookupInput, responses={200: None})
    def post(self, request):
        data = serializers.LookupInput(data=request.data)
        data.is_valid(raise_exception=True)
        user, is_member = services.lookup_admission_identity(
            library=request.user.library,
            phone=data.validated_data["phone"],
            email=data.validated_data.get("email"),
        )
        if user is None:
            return ok({"match": "none"})
        return ok({"match": "existing", "student": serializers.masked_student(user, is_member_here=is_member)})


class AdmissionView(APIView):
    """#54: offline admission, with student, membership and payment in one transaction."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.AdmissionInput, responses={201: None})
    def post(self, request):
        data = serializers.AdmissionInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        result = services.admit_offline_student(
            library=request.user.library,
            owner=request.user,
            student=dict(values["student"]),
            seat_id=values["seat_id"],
            plan_id=values["plan_id"],
            start_date=values.get("start_date"),
            payment=dict(values["payment"]),
        )
        student = result.student
        return created(
            {
                "student": {
                    "id": str(student.pk),
                    "name": student.name,
                    "is_offline": student.is_offline,
                    "created": result.created,
                },
                "membership": serializers.member_row(_annotated(result.membership)),
                "payment": serializers.payment_row(result.payment),
            }
        )


class StudentMembershipListView(APIView):
    """#56: the signed-in student's own memberships."""

    permission_classes = [IsAuthenticated, IsStudent]

    @extend_schema(
        operation_id="student_memberships_list", parameters=[serializers.StudentMembershipQuery], responses={200: None}
    )
    def get(self, request):
        query = serializers.StudentMembershipQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = selectors.student_memberships(request.user, include_archived=query.validated_data["include_archived"])
        return ok([serializers.student_membership_row(m) for m in rows])


class StudentMembershipDetailView(APIView):
    """#57: the membership card with its payment history."""

    permission_classes = [IsAuthenticated, IsStudent]

    @extend_schema(responses={200: None})
    def get(self, request, membership_id):
        membership = selectors.student_membership(request.user, membership_id)
        if membership is None:
            raise NotFound()
        payments = payment_selectors.membership_payments(membership)
        return ok(serializers.student_membership_detail(membership, payments))
