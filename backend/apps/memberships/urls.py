from django.urls import path

from . import views

urlpatterns = [
    path("owner/members/", views.OwnerMemberListView.as_view(), name="owner-member-list"),
    path("owner/members/<uuid:membership_id>/", views.OwnerMemberDetailView.as_view(), name="owner-member-detail"),
    path("owner/members/<uuid:membership_id>/renewals/", views.OwnerRenewalView.as_view(), name="owner-member-renew"),
    path("owner/members/<uuid:membership_id>/archive/", views.OwnerArchiveView.as_view(), name="owner-member-archive"),
    path("owner/dues/", views.OwnerDuesView.as_view(), name="owner-dues"),
    path("owner/admissions/lookup/", views.AdmissionLookupView.as_view(), name="owner-admission-lookup"),
    path("owner/admissions/", views.AdmissionView.as_view(), name="owner-admission-create"),
    path("student/memberships/", views.StudentMembershipListView.as_view(), name="student-membership-list"),
    path(
        "student/memberships/<uuid:membership_id>/",
        views.StudentMembershipDetailView.as_view(),
        name="student-membership-detail",
    ),
]
