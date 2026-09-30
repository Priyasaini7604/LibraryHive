from django.urls import path
from .views import ComplaintCreateView, MyComplaintsView, LibraryComplaintsView, ComplaintResolveView

urlpatterns = [
    path("", ComplaintCreateView.as_view(), name="complaint-create"),
    path("me/", MyComplaintsView.as_view(), name="my-complaints"),
    path("<uuid:pk>/", ComplaintResolveView.as_view(), name="complaint-resolve"),
    path("library/<uuid:library_id>/", LibraryComplaintsView.as_view(), name="library-complaints"),
]