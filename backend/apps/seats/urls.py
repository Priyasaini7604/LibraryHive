from django.urls import path

from . import views

urlpatterns = [
    path("owner/seats/", views.OwnerSeatListView.as_view(), name="owner-seat-list"),
    path("owner/seats/<uuid:seat_id>/", views.OwnerSeatDetailView.as_view(), name="owner-seat-detail"),
    path("owner/seats/<uuid:seat_id>/enable/", views.OwnerSeatEnableView.as_view(), name="owner-seat-enable"),
]
