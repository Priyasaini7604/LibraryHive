from django.urls import path

from .views import MembershipListView


urlpatterns = [
    path("", MembershipListView.as_view(), name="membership-list"),
]