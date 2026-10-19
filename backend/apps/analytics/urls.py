from django.urls import path

from . import views

urlpatterns = [
    path("owner/dashboard/", views.OwnerDashboardView.as_view(), name="owner-dashboard"),
    path("owner/reports/occupancy/", views.OccupancyReportView.as_view(), name="report-occupancy"),
    path("owner/reports/revenue/", views.RevenueReportView.as_view(), name="report-revenue"),
    path("owner/reports/complaints/", views.ComplaintReportView.as_view(), name="report-complaints"),
    path("owner/reports/domains/", views.DomainReportView.as_view(), name="report-domains"),
    path("owner/exports/members.csv", views.MembersExportView.as_view(), name="export-members"),
    path("owner/exports/payments.csv", views.PaymentsExportView.as_view(), name="export-payments"),
    path("owner/exports/attendance.csv", views.AttendanceExportView.as_view(), name="export-attendance"),
    path("owner/audit-log/", views.AuditLogView.as_view(), name="owner-audit-log"),
    path("student/dashboard/", views.StudentDashboardView.as_view(), name="student-dashboard"),
]
