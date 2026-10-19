from django.urls import path

from . import views

urlpatterns = [
    path("libraries/", views.PublicLibraryListView.as_view(), name="library-list"),
    path("libraries/<uuid:library_id>/", views.PublicLibraryDetailView.as_view(), name="library-detail"),
    path("owner/library/", views.OwnerLibraryView.as_view(), name="owner-library"),
    path("owner/library/plans/", views.OwnerPlanListView.as_view(), name="owner-plan-list"),
    path("owner/library/plans/<uuid:plan_id>/", views.OwnerPlanDetailView.as_view(), name="owner-plan-detail"),
    path(
        "owner/library/plans/<uuid:plan_id>/deactivate/",
        views.OwnerPlanDeactivateView.as_view(),
        name="owner-plan-deactivate",
    ),
    path(
        "owner/library/plans/<uuid:plan_id>/activate/",
        views.OwnerPlanActivateView.as_view(),
        name="owner-plan-activate",
    ),
    path("owner/library/photos/", views.OwnerPhotoListView.as_view(), name="owner-photo-list"),
    path("owner/library/photos/<uuid:photo_id>/", views.OwnerPhotoDetailView.as_view(), name="owner-photo-detail"),
    path(
        "owner/library/photos/<uuid:photo_id>/set-cover/",
        views.OwnerPhotoSetCoverView.as_view(),
        name="owner-photo-set-cover",
    ),
]
