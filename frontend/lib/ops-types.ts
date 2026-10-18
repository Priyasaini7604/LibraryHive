/**
 * Types for seats, memberships, payments, attendance, complaints, visits, dashboards and notifications
 * (BACKEND_ARCHITECTURE.md #16, #30-#89). Re-exported from lib/types.ts.
 */

import type { Page, PublishChecklist, SeatCounts } from "./types";

/** Seats and holds. Seat status is derived by the server, never stored. */

export type SeatStatus = "empty" | "reserved" | "occupied" | "disabled";

export interface PublicSeat {
  id: string;
  label: string;
  row_label: string;
  position: number | null;
  status: SeatStatus;
}

export interface SeatMap<S> {
  seats: S[];
  counts: SeatCounts;
}

export interface OwnerSeat {
  id: string;
  label: string;
  row_label: string;
  position: number | null;
  is_active: boolean;
  is_disabled: boolean;
  disabled_reason: string;
  status: SeatStatus | null;
  occupant: { membership_id: string; student_name: string } | null;
  hold: {
    id: string;
    kind: "booking" | "owner_manual";
    student_name?: string;
    expires_at?: string;
    reason?: string;
  } | null;
}

export interface StudentHold {
  id: string;
  seat: { id: string; label: string };
  library: { id: string; name: string };
  plan: { id: string; name: string; duration_days: number; price: string };
  amount: string;
  expires_at: string;
}

/** Memberships, payments and receipts. */

export type MembershipStatus = "active" | "due" | "overdue" | "archived";
export type MembershipSource = "online" | "offline";
export type PaymentMethod = "gateway" | "cash" | "upi_direct" | "bank_transfer";
export type OfflineMethod = Exclude<PaymentMethod, "gateway">;
export type PaymentStatus = "pending" | "success" | "failed" | "cancelled" | "needs_refund";
export type PaymentPurpose = "new_membership" | "renewal";

export interface StudentMembership {
  id: string;
  library: { id: string; name: string };
  seat: { label: string };
  plan: { id: string; name: string; price: string; duration_days: number };
  source: MembershipSource;
  status: MembershipStatus;
  start_date: string;
  next_due_date: string;
  days_to_due: number;
  renewal_open: boolean;
}

export interface PaymentPeriod {
  id: string;
  receipt_number: string;
  purpose: PaymentPurpose;
  channel: "online" | "offline";
  method: PaymentMethod;
  amount: string;
  plan: string;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
}

export interface StudentMembershipDetail extends StudentMembership {
  payments: PaymentPeriod[];
}

export interface StudentPayment {
  id: string;
  library: { id: string; name: string };
  purpose: PaymentPurpose;
  method: PaymentMethod;
  amount: string;
  status: PaymentStatus;
  receipt_number: string;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface StudentReceipt extends StudentPayment {
  library_contact: { phone: string | null; email: string | null; address: string };
  plan_name: string;
  seat_label: string | null;
}

export interface OwnerPayment extends StudentPayment {
  channel: "online" | "offline";
  student: { id: string; name: string; phone: string };
  recorded_by: { name: string } | null;
}

export interface OwnerPaymentDetail extends OwnerPayment {
  plan_name: string;
  seat_label: string | null;
  failure_reason: string;
  notes: string;
}

/** What the gateway checkout opens with (#41). The amount always comes from the server. */
export interface PaymentOrder {
  payment_id: string;
  gateway: "razorpay";
  key_id: string;
  order_id: string;
  amount_paise: number;
  currency: "INR";
  description: string;
  prefill: { name: string; email: string; phone: string };
}

export interface VerifyResult {
  payment: {
    id: string;
    status: PaymentStatus;
    receipt_number: string;
    amount: string;
    period_start: string;
    period_end: string;
  };
  membership: {
    id: string;
    seat: { id: string; label: string };
    next_due_date: string;
    status: MembershipStatus;
  } | null;
}

export interface OwnerStudentSummary {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  domain: string | null;
  is_offline: boolean;
}

export interface OwnerMemberHistoryRow {
  membership_id: string;
  seat: { id: string; label: string };
  plan: { id: string; name: string };
  source: MembershipSource;
  status: MembershipStatus;
  start_date: string;
  next_due_date: string;
}

export interface OwnerMember extends OwnerMemberHistoryRow {
  student: OwnerStudentSummary;
}

export interface OwnerMemberDetail extends OwnerMember {
  archived_at: string | null;
  archive_reason: string;
  attendance_summary: { this_month_days: number; last_check_in: string | null };
  complaints_count: number;
  payments: PaymentPeriod[];
  other_memberships_here: OwnerMemberHistoryRow[];
}

export interface DueRow {
  membership_id: string;
  student: { name: string; phone: string };
  seat_label: string;
  plan: { id: string; name: string; price: string };
  status: "due" | "overdue";
  next_due_date: string;
  days_overdue: number;
  amount_due: string;
}

export interface AdmissionLookup {
  match: "none" | "existing";
  student?: {
    id: string;
    name: string;
    masked_phone: string | null;
    masked_email: string | null;
    is_offline: boolean;
    is_member_here: boolean;
  };
}

export interface AdmissionResult {
  student: { id: string; name: string; is_offline: boolean; created: boolean };
  membership: OwnerMember;
  payment: PaymentPeriod;
}

/** Attendance, complaints and visits. */

export interface AttendanceRecord {
  id: string;
  library: { id: string; name: string };
  seat_label: string | null;
  date: string;
  check_in_at: string;
  check_out_at: string | null;
  duration_minutes: number | null;
  check_in_method: "self" | "owner";
  check_out_method: "self" | "owner" | "auto" | null;
  status: "open" | "closed" | "auto_closed";
}

export interface OwnerAttendanceRecord extends AttendanceRecord {
  student: { id: string; name: string };
}

export interface AttendanceHistory extends Page<AttendanceRecord> {
  summary: { days_present: number; total_minutes: number };
}

export interface LiveAttendanceRow {
  record_id: string;
  student: { id: string; name: string };
  seat_label: string | null;
  check_in_at: string;
}

export type ComplaintCategory =
  | "noise"
  | "ac"
  | "wifi"
  | "cleanliness"
  | "power_lighting"
  | "seat_furniture"
  | "staff"
  | "other";
export type ComplaintStatus = "open" | "in_progress" | "resolved";

export interface Complaint {
  id: string;
  library: { id: string; name: string };
  category: ComplaintCategory;
  description: string;
  status: ComplaintStatus;
  owner_response: string;
  responded_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface OwnerComplaint extends Complaint {
  student: { id: string; name: string };
  seat_label: string | null;
}

export type VisitSlot = "morning" | "afternoon" | "evening";
export type VisitStatus = "pending" | "accepted" | "rejected" | "cancelled";

export interface Visit {
  id: string;
  library: { id: string; name: string };
  preferred_date: string;
  preferred_slot: VisitSlot;
  student_note: string;
  status: VisitStatus;
  owner_note: string;
  decided_at: string | null;
  created_at: string;
}

export interface OwnerVisit extends Visit {
  student: { id: string; name: string; phone: string };
}

/** Dashboards, reports and notifications. */

export interface OwnerDashboard {
  seats: { total: number; empty: number; reserved: number; occupied: number; disabled: number };
  members: { active: number; due: number; overdue: number };
  today: { new_bookings: number; check_ins: number; present_now: number };
  upcoming_renewals_7d: number;
  revenue: { this_month_total: string; by_method: Record<string, { total: string; count: number }> };
  open_complaints: number;
  pending_visits: number;
  domain_breakdown: { code: string; name: string; count: number }[];
  publish_checklist: PublishChecklist;
}

export interface StudentDashboard {
  memberships: StudentMembership[];
  current_attendance: AttendanceRecord | null;
  recent_payments: StudentPayment[];
  open_complaints: number;
  visits: {
    id: string;
    library: { id: string; name: string };
    preferred_date: string;
    preferred_slot: VisitSlot;
    status: VisitStatus;
  }[];
  pending_hold: {
    id: string;
    library: { id: string; name: string };
    seat_label: string;
    plan: { id: string; name: string };
    expires_at: string;
  } | null;
}

export interface OccupancyReport {
  counts: SeatCounts;
  by_row: { row_label: string; total: number; occupied: number; reserved: number; empty: number }[];
}

export interface RevenueBucket {
  total: string;
  count: number;
}

export interface RevenueReport {
  total: string;
  count: number;
  by_method: Record<string, RevenueBucket>;
  by_purpose: Record<string, RevenueBucket>;
  by_month: { month: string; total: string; count: number }[];
}

export interface ComplaintReport {
  by_status: Record<string, number>;
  by_category: Record<string, number>;
}

export interface AuditEntry {
  id: string;
  created_at: string;
  actor: { name: string; role: string };
  action: string;
  entity_type: string;
  entity_id: string;
  changes: Record<string, unknown>;
  reason: string;
}

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
  read_at: string | null;
}
