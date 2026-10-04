from django.urls import path
from .views import (
    LibraryListCreateView,
    LibraryDetailView,
    OwnerLibraryMeView,
    LibraryDomainBreakdownView,
)
from apps.seats.views import LibrarySeatsView

urlpatterns = [
    path("", LibraryListCreateView.as_view(), name="library-list-create"),
    path("me/", OwnerLibraryMeView.as_view(), name="owner-library-me"),
    path("<uuid:id>/", LibraryDetailView.as_view(), name="library-detail"),
    path("<uuid:id>/domain-breakdown/", LibraryDomainBreakdownView.as_view(), name="library-domain-breakdown"),
    path("<uuid:library_id>/seats/", LibrarySeatsView.as_view(), name="library-seats"),
]
