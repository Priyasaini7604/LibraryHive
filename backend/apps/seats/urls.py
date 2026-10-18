from django.urls import path

from . import views

urlpatterns = [
    path("owner/seats/", views.OwnerSeatListView.as_view(), name="owner-seat-list"),
    path("owner/seats/<uuid:seat_id>/", views.OwnerSeatDetailView.as_view(), name="owner-seat-detail"),
    path("owner/seats/<uuid:seat_id>/enable/", views.OwnerSeatEnableView.as_view(), name="owner-seat-enable"),
    path("owner/seats/<uuid:seat_id>/manual-hold/", views.OwnerManualHoldView.as_view(), name="owner-seat-manual-hold"),
    path("owner/holds/<uuid:hold_id>/release/", views.OwnerHoldReleaseView.as_view(), name="owner-hold-release"),
    path("student/holds/", views.StudentHoldCreateView.as_view(), name="student-hold-create"),
    path("student/holds/current/", views.StudentCurrentHoldsView.as_view(), name="student-hold-current"),
    path("student/holds/<uuid:hold_id>/cancel/", views.StudentHoldCancelView.as_view(), name="student-hold-cancel"),
]
