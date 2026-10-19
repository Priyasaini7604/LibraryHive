"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { createBookingOrder, createRenewalOrder, fetchStudentPayments, verifyPayment } from "@/lib/api/payments";
import { isApiError, userMessage } from "@/lib/errors";
import { openCheckout, type RazorpaySuccess } from "@/lib/razorpay";
import type { PaymentOrder, VerifyResult } from "@/lib/types";

/** The checkout page states (UI_ARCHITECTURE.md 5.3). They are derived from the server, never stored. */
export type FlowState =
  | { kind: "ready" }
  | { kind: "creating_order" }
  | { kind: "awaiting_payment" }
  | { kind: "verifying" }
  | { kind: "success"; result: VerifyResult }
  | { kind: "confirming_slow"; orderId: string }
  | { kind: "confirm_timeout"; orderId: string }
  | { kind: "dismissed" }
  | { kind: "failed"; message: string }
  | { kind: "seat_lost"; receipt: string | null }
  | { kind: "expired" };

const POLL_EVERY_MS = 3_000;
const POLL_FOR_MS = 90_000;

export type OrderSource = { hold: string } | { membership: string; plan?: string };

function isTransient(error: unknown): boolean {
  return isApiError(error) && (error.status === 0 || error.status >= 500);
}

/**
 * Runs one payment: create the order on the server, open the gateway window, then have the server verify the
 * result. If verification cannot be reached after the student paid, it keeps asking the server by order id
 * (every 3 s for up to 90 s) and never asks the student to pay again.
 */
export function usePaymentFlow(source: OrderSource, onPaid?: () => void) {
  const [state, setState] = useState<FlowState>({ kind: "ready" });
  const orderRef = useRef<PaymentOrder | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const set = useCallback((next: FlowState) => {
    if (alive.current) setState(next);
  }, []);

  const finish = useCallback(
    (result: VerifyResult) => {
      set({ kind: "success", result });
      onPaid?.();
    },
    [onPaid, set],
  );

  const confirmSlowly = useCallback(
    async (orderId: string) => {
      set({ kind: "confirming_slow", orderId });
      const deadline = Date.now() + POLL_FOR_MS;
      while (alive.current && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, POLL_EVERY_MS));
        if (!alive.current) return;
        try {
          const page = await fetchStudentPayments({ order_id: orderId });
          const payment = page.items[0];
          if (payment?.status === "success") {
            return finish({
              payment: {
                id: payment.id,
                status: payment.status,
                receipt_number: payment.receipt_number,
                amount: payment.amount,
                period_start: payment.period_start ?? "",
                period_end: payment.period_end ?? "",
              },
              membership: null,
            });
          }
          if (payment?.status === "needs_refund") return set({ kind: "seat_lost", receipt: payment.receipt_number });
        } catch {
          // keep trying until the deadline
        }
      }
      set({ kind: "confirm_timeout", orderId });
    },
    [finish, set],
  );

  const verify = useCallback(
    async (result: RazorpaySuccess) => {
      set({ kind: "verifying" });
      try {
        finish(await verifyPayment(result));
      } catch (error) {
        if (isApiError(error, "SEAT_LOST_REFUND_PENDING")) set({ kind: "seat_lost", receipt: null });
        else if (isTransient(error)) void confirmSlowly(result.razorpay_order_id);
        else set({ kind: "failed", message: userMessage(error) });
      }
    },
    [confirmSlowly, finish, set],
  );

  const start = useCallback(async () => {
    set({ kind: "creating_order" });
    let order: PaymentOrder;
    try {
      order = await ("hold" in source
        ? createBookingOrder(source.hold)
        : createRenewalOrder(source.membership, source.plan));
    } catch (error) {
      if (isApiError(error, "HOLD_EXPIRED")) return set({ kind: "expired" });
      return set({ kind: "failed", message: userMessage(error) });
    }
    orderRef.current = order;
    set({ kind: "awaiting_payment" });
    try {
      await openCheckout(order, {
        onSuccess: (result) => void verify(result),
        onDismiss: () => setState((current) => (current.kind === "awaiting_payment" ? { kind: "dismissed" } : current)),
        onFailure: (message) => set({ kind: "failed", message }),
      });
    } catch {
      set({ kind: "failed", message: "Payment could not be opened. Check your connection and try again." });
    }
  }, [source, set, verify]);

  return { state, start, reset: () => set({ kind: "ready" }), markExpired: () => set({ kind: "expired" }) };
}
