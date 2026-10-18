/** Attendance, complaints, visits, notifications, dashboards and reports (BACKEND_ARCHITECTURE.md #58-#89). */

import { api, downloadFile } from "../api-client";
import type {
  AppNotification,
  AttendanceHistory,
  AttendanceRecord,
  AuditEntry,
  Complaint,
  ComplaintCategory,
  ComplaintReport,
  ComplaintStatus,
  LiveAttendanceRow,
  OccupancyReport,
  OwnerAttendanceRecord,
  OwnerComplaint,
  OwnerDashboard,
  OwnerVisit,
  Page,
  RevenueReport,
  StudentDashboard,
  Visit,
  VisitSlot,
  VisitStatus,
} from "../types";

/* Attendance (#62-#70) */

export function checkIn(libraryId: string): Promise<AttendanceRecord> {
  return api.post<AttendanceRecord>("/student/attendance/check-in/", { library_id: libraryId });
}

export function checkOut(): Promise<AttendanceRecord> {
  return api.post<AttendanceRecord>("/student/attendance/check-out/");
}

export function fetchCurrentAttendance(): Promise<AttendanceRecord | null> {
  return api.get<AttendanceRecord | null>("/student/attendance/current/");
}

export function fetchAttendanceHistory(query: { month?: string; page?: number } = {}): Promise<AttendanceHistory> {
  return api.get<AttendanceHistory>("/student/attendance/", { query });
}

export function fetchLiveAttendance(): Promise<LiveAttendanceRow[]> {
  return api.get<LiveAttendanceRow[]>("/owner/attendance/live/");
}

export function fetchOwnerAttendance(
  query: { date?: string; from?: string; to?: string; student_id?: string; page?: number } = {},
): Promise<Page<OwnerAttendanceRecord>> {
  return api.get<Page<OwnerAttendanceRecord>>("/owner/attendance/", { query });
}

export function ownerCheckIn(membershipId: string): Promise<OwnerAttendanceRecord> {
  return api.post<OwnerAttendanceRecord>("/owner/attendance/check-in/", { membership_id: membershipId });
}

export function ownerCheckOut(recordId: string): Promise<OwnerAttendanceRecord> {
  return api.post<OwnerAttendanceRecord>(`/owner/attendance/${recordId}/check-out/`);
}

export function correctAttendance(
  recordId: string,
  input: { check_in_at?: string; check_out_at?: string; reason: string },
): Promise<OwnerAttendanceRecord> {
  return api.patch<OwnerAttendanceRecord>(`/owner/attendance/${recordId}/`, input);
}

/* Complaints (#71-#76) */

export function raiseComplaint(input: { library_id: string; category: ComplaintCategory; description: string }): Promise<Complaint> {
  return api.post<Complaint>("/student/complaints/", input);
}

export function fetchStudentComplaints(query: { status?: ComplaintStatus; page?: number } = {}): Promise<Page<Complaint>> {
  return api.get<Page<Complaint>>("/student/complaints/", { query });
}

export function fetchStudentComplaint(id: string): Promise<Complaint> {
  return api.get<Complaint>(`/student/complaints/${id}/`);
}

export function fetchOwnerComplaints(
  query: { status?: ComplaintStatus; category?: ComplaintCategory; page?: number } = {},
): Promise<Page<OwnerComplaint>> {
  return api.get<Page<OwnerComplaint>>("/owner/complaints/", { query });
}

export function fetchOwnerComplaint(id: string): Promise<OwnerComplaint> {
  return api.get<OwnerComplaint>(`/owner/complaints/${id}/`);
}

export function respondToComplaint(
  id: string,
  input: { status?: "in_progress" | "resolved"; owner_response?: string },
): Promise<OwnerComplaint> {
  return api.patch<OwnerComplaint>(`/owner/complaints/${id}/`, input);
}

/* Visits (#77-#81) */

export function requestVisit(input: {
  library_id: string;
  preferred_date: string;
  preferred_slot: VisitSlot;
  student_note?: string;
}): Promise<Visit> {
  return api.post<Visit>("/student/visits/", input);
}

export function fetchStudentVisits(query: { status?: VisitStatus; page?: number } = {}): Promise<Page<Visit>> {
  return api.get<Page<Visit>>("/student/visits/", { query });
}

export function cancelVisit(id: string): Promise<Visit> {
  return api.post<Visit>(`/student/visits/${id}/cancel/`);
}

export function fetchOwnerVisits(
  query: { status?: VisitStatus; from?: string; to?: string; page?: number } = {},
): Promise<Page<OwnerVisit>> {
  return api.get<Page<OwnerVisit>>("/owner/visits/", { query });
}

export function decideVisit(id: string, input: { decision: "accept" | "reject"; owner_note?: string }): Promise<OwnerVisit> {
  return api.post<OwnerVisit>(`/owner/visits/${id}/decision/`, input);
}

/* Notifications (#58-#61) */

export function fetchNotifications(query: { unread?: boolean; page?: number } = {}): Promise<Page<AppNotification>> {
  return api.get<Page<AppNotification>>("/notifications/", { query: { unread: query.unread ? "true" : undefined, page: query.page } });
}

export async function fetchUnreadCount(): Promise<number> {
  return (await api.get<{ count: number }>("/notifications/unread-count/")).count;
}

export function markNotificationRead(id: string): Promise<AppNotification> {
  return api.post<AppNotification>(`/notifications/${id}/read/`);
}

export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return api.post<{ updated: number }>("/notifications/read-all/");
}

/* Dashboards, reports, exports, activity (#82-#89) */

export function fetchOwnerDashboard(): Promise<OwnerDashboard> {
  return api.get<OwnerDashboard>("/owner/dashboard/");
}

export function fetchStudentDashboard(): Promise<StudentDashboard> {
  return api.get<StudentDashboard>("/student/dashboard/");
}

export function fetchOccupancyReport(): Promise<OccupancyReport> {
  return api.get<OccupancyReport>("/owner/reports/occupancy/");
}

export function fetchRevenueReport(range: { from: string; to: string }): Promise<RevenueReport> {
  return api.get<RevenueReport>("/owner/reports/revenue/", { query: range });
}

export function fetchComplaintReport(range: { from?: string; to?: string } = {}): Promise<ComplaintReport> {
  return api.get<ComplaintReport>("/owner/reports/complaints/", { query: range });
}

export function fetchDomainReport(): Promise<{ code: string; name: string; count: number }[]> {
  return api.get("/owner/reports/domains/");
}

export type ExportKind = "members" | "payments" | "attendance";

/** Download a CSV through the authenticated client (the token is in memory, so a plain link would not work). */
export function downloadExport(kind: ExportKind, query: { from?: string; to?: string; status?: string } = {}) {
  return downloadFile(`/owner/exports/${kind}.csv`, query);
}

export function fetchAuditLog(
  query: { action?: string; entity_type?: string; from?: string; to?: string; page?: number } = {},
): Promise<Page<AuditEntry>> {
  return api.get<Page<AuditEntry>>("/owner/audit-log/", { query });
}
