/** Direct UPI payments with manual owner approval (SPEC.md 3.11b-c; BACKEND_ARCHITECTURE.md 9.7b). */

export type UpiRequestStatus = "pending" | "approved" | "rejected" | "cancelled";

/** The owner's own settings. `qr_url` is a short-lived signed link, never a permanent address. */
export interface UpiPaymentSettings {
  upi_enabled: boolean;
  upi_id: string;
  instructions: string;
  has_qr: boolean;
  qr_url: string | null;
  qr_url_expires_in?: number | null;
}

export interface UpiSettingsInput {
  upi_enabled?: boolean;
  upi_id?: string;
  instructions?: string;
}

/** What a paying student sees. Only returned with a live hold or an active membership at that library. */
export interface UpiPaymentInfo {
  library: { id: string; name: string; contact_phone: string | null; contact_email: string | null };
  upi_id: string;
  instructions: string;
  qr_url: string | null;
  qr_url_expires_in: number | null;
}

interface UpiRequestBase {
  id: string;
  status: UpiRequestStatus;
  purpose: "new_membership" | "renewal";
  amount: string;
  utr: string;
  student_note: string;
  has_screenshot: boolean;
  plan: { id: string; name: string; duration_days: number };
  seat: { id: string; label: string } | null;
  created_at: string;
  /** Hours a pending request has waited (null once decided). */
  waiting_hours: number | null;
  /** Pending for longer than the review target (default 24 h). Nothing is decided automatically. */
  overdue: boolean;
  reviewed_at: string | null;
  review_note: string;
  receipt_number: string | null;
}

export interface StudentUpiRequest extends UpiRequestBase {
  library: { id: string; name: string; contact_phone: string | null; contact_email: string | null };
  can_cancel: boolean;
}

export interface OwnerUpiRequest extends UpiRequestBase {
  student: { id: string; name: string; phone: string };
  reviewed_by: string | null;
}

/** Either a booking hold or a membership being renewed. The amount is never sent: the server reads it. */
export type UpiSource = { hold: string } | { membership: string; plan?: string };

export interface UpiSubmitInput {
  utr: string;
  note?: string;
  screenshot?: File | null;
}

export interface UpiPendingSummary {
  pending: number;
  overdue: number;
}

export interface PrivateImageLink {
  url: string;
  expires_in: number;
}
