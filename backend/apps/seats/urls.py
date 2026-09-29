from django.urls import path
from .views import SeatDetailView, LibrarySeatsView

urlpatterns = [
    path("<uuid:id>/", SeatDetailView.as_view(), name="seat-detail"),
    path("library/<uuid:library_id>/", LibrarySeatsView.as_view(), name="library-seats-direct"),
]
