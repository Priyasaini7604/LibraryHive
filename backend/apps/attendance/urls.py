from django.urls import path

from . import views

urlpatterns = [
    path("student/attendance/check-in/", views.StudentCheckInView.as_view(), name="attendance-check-in"),
    path("student/attendance/check-out/", views.StudentCheckOutView.as_view(), name="attendance-check-out"),
    path("student/attendance/current/", views.StudentCurrentView.as_view(), name="attendance-current"),
    path("student/attendance/", views.StudentAttendanceView.as_view(), name="attendance-student-list"),
    path("owner/attendance/live/", views.OwnerLiveView.as_view(), name="attendance-owner-live"),
    path("owner/attendance/check-in/", views.OwnerCheckInView.as_view(), name="attendance-owner-check-in"),
    path(
        "owner/attendance/<uuid:record_id>/check-out/",
        views.OwnerCheckOutView.as_view(),
        name="attendance-owner-check-out",
    ),
    path("owner/attendance/<uuid:record_id>/", views.OwnerCorrectionView.as_view(), name="attendance-owner-correct"),
    path("owner/attendance/", views.OwnerAttendanceView.as_view(), name="attendance-owner-list"),
]
