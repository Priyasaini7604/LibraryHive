"""Complaint endpoints #71-#76 (BACKEND_ARCHITECTURE.md 9.10)."""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.exceptions import NotFound
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import created, ok

from . import selectors, serializers, services

STUDENT = [IsAuthenticated, IsStudent]
OWNER = [IsAuthenticated, IsOwner, HasLibrary]


def _page(request, queryset, row):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([row(item) for item in page])


class StudentComplaintListView(APIView):
    """#71 (create) and #72 (own list)."""

    permission_classes = STUDENT
    parser_classes = [JSONParser]

    @extend_schema(operation_id="student_complaints_list", parameters=[serializers.StudentQuery], responses={200: None})
    def get(self, request):
        query = serializers.StudentQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.student_complaints(request.user, status=query.validated_data.get("status"))
        return _page(request, queryset, serializers.student_row)

    @extend_schema(request=serializers.CreateComplaintInput, responses={201: None})
    def post(self, request):
        data = serializers.CreateComplaintInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        complaint = services.create_complaint(
            student=request.user,
            library_id=values["library_id"],
            category=values["category"],
            description=values["description"],
        )
        return created(serializers.student_row(selectors.student_complaint(request.user, complaint.pk)))


class StudentComplaintDetailView(APIView):
    """#73: one of the student's own complaints."""

    permission_classes = STUDENT

    @extend_schema(responses={200: None})
    def get(self, request, complaint_id):
        complaint = selectors.student_complaint(request.user, complaint_id)
        if complaint is None:
            raise NotFound()
        return ok(serializers.student_row(complaint))


class OwnerComplaintListView(APIView):
    """#74: the owner's complaint inbox."""

    permission_classes = OWNER

    @extend_schema(operation_id="owner_complaints_list", parameters=[serializers.OwnerQuery], responses={200: None})
    def get(self, request):
        query = serializers.OwnerQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.owner_complaints(request.user.library, **query.validated_data)
        return _page(request, queryset, serializers.owner_row)


class OwnerComplaintDetailView(APIView):
    """#75 (detail) and #76 (respond or change status)."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(responses={200: None})
    def get(self, request, complaint_id):
        complaint = selectors.owner_complaint(request.user.library, complaint_id)
        if complaint is None:
            raise NotFound()
        return ok(serializers.owner_row(complaint))

    @extend_schema(request=serializers.RespondInput, responses={200: None})
    def patch(self, request, complaint_id):
        data = serializers.RespondInput(data=request.data)
        data.is_valid(raise_exception=True)
        services.respond(
            library=request.user.library,
            owner=request.user,
            complaint_id=complaint_id,
            status=data.validated_data.get("status"),
            owner_response=data.validated_data.get("owner_response"),
        )
        return ok(serializers.owner_row(selectors.owner_complaint(request.user.library, complaint_id)))
