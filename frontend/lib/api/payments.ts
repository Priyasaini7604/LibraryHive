/** Orders, verification and payment history (BACKEND_ARCHITECTURE.md #41-#47). */

import { api } from "../api-client";
import type {
  OwnerPayment,
  OwnerPaymentDetail,
  Page,
  PaymentMethod,
  PaymentOrder,
  PaymentStatus,
  StudentPayment,
  StudentReceipt,
  VerifyResult,
} from "../types";

/** New booking: the order for a live hold. The amount is never sent. */
export function createBookingOrder(holdId: string): Promise<PaymentOrder> {
  return api.post<PaymentOrder>("/payments/orders/", { hold_id: holdId });
}

/** Renewal: the order for the member's own membership, optionally with a different plan. */
export function createRenewalOrder(membershipId: string, planId?: string): Promise<PaymentOrder> {
  return api.post<PaymentOrder>("/payments/orders/", { membership_id: membershipId, ...(planId ? { plan_id: planId } : {}) });
}

export interface CheckoutResult {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

/** The server checks the signature; a callback alone never confirms anything (#42). */
export function verifyPayment(result: CheckoutResult): Promise<VerifyResult> {
  return api.post<VerifyResult>("/payments/verify/", result);
}

export function fetchStudentPayments(query: { order_id?: string; page?: number } = {}): Promise<Page<StudentPayment>> {
  return api.get<Page<StudentPayment>>("/student/payments/", { query });
}

export function fetchStudentReceipt(paymentId: string): Promise<StudentReceipt> {
  return api.get<StudentReceipt>(`/student/payments/${paymentId}/`);
}

export interface OwnerPaymentFilters {
  status?: PaymentStatus;
  method?: PaymentMethod;
  channel?: "online" | "offline";
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
}

export function fetchOwnerPayments(filters: OwnerPaymentFilters = {}): Promise<Page<OwnerPayment>> {
  return api.get<Page<OwnerPayment>>("/owner/payments/", { query: { ...filters } });
}

export function fetchOwnerPayment(paymentId: string): Promise<OwnerPaymentDetail> {
  return api.get<OwnerPaymentDetail>(`/owner/payments/${paymentId}/`);
}
