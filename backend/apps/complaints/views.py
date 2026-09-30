from django.utils import timezone
from rest_framework import generics, permissions
from .models import Complaint
from .serializers import ComplaintCreateSerializer, ComplaintListSerializer, ComplaintResolveSerializer


class ComplaintCreateView(generics.CreateAPIView):
    """Student raises a complaint — POST /api/complaints/"""
    serializer_class = ComplaintCreateSerializer
    permission_classes = [permissions.IsAuthenticated]


class MyComplaintsView(generics.ListAPIView):
    """Student sees their own complaints — GET /api/complaints/me/"""
    serializer_class = ComplaintListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Complaint.objects.filter(student=self.request.user)


class LibraryComplaintsView(generics.ListAPIView):
    """Owner sees complaints for their library — GET /api/libraries/<id>/complaints/"""
    serializer_class = ComplaintListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        library_id = self.kwargs["library_id"]
        qs = Complaint.objects.filter(library_id=library_id, library__owner=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class ComplaintResolveView(generics.UpdateAPIView):
    """Owner updates/resolves a complaint — PATCH /api/complaints/<id>/"""
    serializer_class = ComplaintResolveSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Complaint.objects.all()

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status == "resolved" and not instance.resolved_at:
            instance.resolved_at = timezone.now()
            instance.save()
