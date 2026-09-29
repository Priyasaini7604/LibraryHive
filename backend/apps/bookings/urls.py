from django.urls import path

from .views import BookingExpireView, BookingListCreateView


urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("expire/", BookingExpireView.as_view(), name="booking-expire"),
]