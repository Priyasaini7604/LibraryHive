from django.urls import path

from . import views

urlpatterns = [
    path("student/visits/", views.StudentVisitListView.as_view(), name="visit-student-list"),
    path("student/visits/<uuid:visit_id>/cancel/", views.StudentVisitCancelView.as_view(), name="visit-student-cancel"),
    path("owner/visits/", views.OwnerVisitListView.as_view(), name="visit-owner-list"),
    path("owner/visits/<uuid:visit_id>/decision/", views.OwnerVisitDecisionView.as_view(), name="visit-owner-decision"),
]
