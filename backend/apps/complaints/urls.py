from django.urls import path

from . import views

urlpatterns = [
    path("student/complaints/", views.StudentComplaintListView.as_view(), name="complaint-student-list"),
    path(
        "student/complaints/<uuid:complaint_id>/",
        views.StudentComplaintDetailView.as_view(),
        name="complaint-student-detail",
    ),
    path("owner/complaints/", views.OwnerComplaintListView.as_view(), name="complaint-owner-list"),
    path(
        "owner/complaints/<uuid:complaint_id>/", views.OwnerComplaintDetailView.as_view(), name="complaint-owner-detail"
    ),
]
