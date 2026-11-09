/** Direct UPI payments: settings, QR, requests and review (BACKEND_ARCHITECTURE.md 9.7b). */

import { api } from "../api-client";
import type {
  OwnerUpiRequest,
  Page,
  PrivateImageLink,
  StudentUpiRequest,
  UpiPaymentInfo,
  UpiPaymentSettings,
  UpiPendingSummary,
  UpiRequestStatus,
  UpiSettingsInput,
  UpiSource,
  UpiSubmitInput,
} from "../types";

// --- Owner -------------------------------------------------------------------------------------------------

export function fetchUpiSettings(): Promise<UpiPaymentSettings> {
  return api.get<UpiPaymentSettings>("/owner/payment-settings/");
}

export function saveUpiSettings(input: UpiSettingsInput): Promise<UpiPaymentSettings> {
  return api.patch<UpiPaymentSettings>("/owner/payment-settings/", input);
}

export function uploadUpiQr(file: File): Promise<UpiPaymentSettings> {
  const body = new FormData();
  body.append("image", file);
  return api.post<UpiPaymentSettings>("/owner/payment-settings/qr/", body);
}

export function removeUpiQr(): Promise<UpiPaymentSettings> {
  return api.delete<UpiPaymentSettings>("/owner/payment-settings/qr/");
}

export function fetchOwnerUpiRequests(query: { status?: UpiRequestStatus; page?: number } = {}): Promise<Page<OwnerUpiRequest>> {
  return api.get<Page<OwnerUpiRequest>>("/owner/upi-payments/", { query });
}

/** How many requests wait for the owner (navigation badge). */
export function fetchOwnerUpiSummary(): Promise<UpiPendingSummary> {
  return api.get<UpiPendingSummary>("/owner/upi-payments/summary/");
}

export function approveUpiRequest(id: string, seatId?: string): Promise<OwnerUpiRequest> {
  return api.post<OwnerUpiRequest>(`/owner/upi-payments/${id}/approve/`, seatId ? { seat_id: seatId } : {});
}

export function rejectUpiRequest(id: string, reason: string): Promise<OwnerUpiRequest> {
  return api.post<OwnerUpiRequest>(`/owner/upi-payments/${id}/reject/`, { reason });
}

export function fetchOwnerUpiScreenshot(id: string): Promise<PrivateImageLink> {
  return api.get<PrivateImageLink>(`/owner/upi-payments/${id}/screenshot/`);
}

// --- Student -----------------------------------------------------------------------------------------------

export function fetchUpiInfo(libraryId: string): Promise<UpiPaymentInfo> {
  return api.get<UpiPaymentInfo>(`/student/libraries/${libraryId}/upi-info/`);
}

/** Sends the UTR (and an optional screenshot). It confirms nothing: the owner decides. */
export function submitUpiRequest(source: UpiSource, input: UpiSubmitInput): Promise<StudentUpiRequest> {
  const body = new FormData();
  if ("hold" in source) body.append("hold_id", source.hold);
  else {
    body.append("membership_id", source.membership);
    if (source.plan) body.append("plan_id", source.plan);
  }
  body.append("utr", input.utr);
  if (input.note) body.append("note", input.note);
  if (input.screenshot) body.append("screenshot", input.screenshot);
  return api.post<StudentUpiRequest>("/student/upi-payments/", body);
}

export function fetchStudentUpiRequests(query: { page?: number } = {}): Promise<Page<StudentUpiRequest>> {
  return api.get<Page<StudentUpiRequest>>("/student/upi-payments/", { query });
}

export function cancelUpiRequest(id: string): Promise<StudentUpiRequest> {
  return api.post<StudentUpiRequest>(`/student/upi-payments/${id}/cancel/`, {});
}
