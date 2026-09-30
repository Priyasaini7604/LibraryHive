from django.urls import path

from .views import (
    NotificationListView,
    NotificationMarkReadView,
)


urlpatterns = [
    path(
        "",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "<uuid:notification_id>/read/",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
]