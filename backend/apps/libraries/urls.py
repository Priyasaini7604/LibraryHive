from django.urls import path
from .views import (
    LibraryListCreateView,
    LibraryDetailView,
    OwnerLibraryMeView,
)
from apps.seats.views import LibrarySeatsView

urlpatterns = [
    path("", LibraryListCreateView.as_view(), name="library-list-create"),
    path("me/", OwnerLibraryMeView.as_view(), name="owner-library-me"),
    path("<uuid:id>/", LibraryDetailView.as_view(), name="library-detail"),
    path("<uuid:library_id>/seats/", LibrarySeatsView.as_view(), name="library-seats"),
]
