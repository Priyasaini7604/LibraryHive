"use client";

import { CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/surface";
import { formatDate } from "@/lib/format";

import type { FlowState } from "./use-payment-flow";

/**
 * What the student sees once payment has started (UI_ARCHITECTURE.md 5.3). `ready`, `dismissed` and `failed`
 * are handled by the caller, which shows the summary and the pay button again.
 */
export function PaymentOutcome({
  state,
  seatLabel,
  libraryHref,
  successTitle,
}: {
  state: FlowState;
  seatLabel?: string;
  libraryHref: string;
  successTitle: string;
}) {
  switch (state.kind) {
    case "creating_order":
      return (
        <p role="status" className="flex items-center gap-2 text-slate-700">
          <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Preparing your payment…
        </p>
      );
    case "awaiting_payment":
      return (
        <p role="status" className="rounded-lg bg-blue-50 p-4 text-blue-900">
          Complete the payment in the payment window. Please don&apos;t close this page.
        </p>
      );
    case "verifying":
      return (
        <p role="status" className="flex items-center gap-2 rounded-lg bg-blue-50 p-4 text-blue-900">
          <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Confirming your payment…
        </p>
      );
    case "confirming_slow":
      return (
        <Alert tone="warning" title="We're confirming your payment">
          Do not pay again. This can take a minute. We&apos;ll update this page as soon as the payment is confirmed.
        </Alert>
      );
    case "confirm_timeout":
      return (
        <Alert
          tone="warning"
          title="Your payment is still being confirmed"
          action={
            <Button asChild variant="secondary" size="sm">
              <Link href="/student/payments">My payments</Link>
            </Button>
          }
        >
          Do not pay again. If money was deducted it will be sorted out automatically. Check My payments in a few minutes
          and contact the library if it still isn&apos;t confirmed. Reference: {state.orderId}
        </Alert>
      );
    case "seat_lost":
      return (
        <Alert tone="danger" title="Your payment was received but the seat was taken">
          The library will refund you. {state.receipt && `Receipt number: ${state.receipt}.`}
        </Alert>
      );
    case "expired":
      return (
        <div className="flex flex-col items-start gap-3">
          <Alert tone="warning" title="Your hold expired">
            The seat was released so others can book it. If you paid, you will be told here and by notification.
          </Alert>
          <Button asChild>
            <Link href={libraryHref}>Choose a seat again</Link>
          </Button>
        </div>
      );
    case "success":
      return (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-emerald-300 bg-emerald-50 p-6" role="status">
          <CheckCircle2 aria-hidden="true" className="size-8 text-emerald-700" />
          <h2 className="text-lg font-semibold text-emerald-900">{successTitle}</h2>
          <p className="text-emerald-900">
            {seatLabel && <>Seat {seatLabel} · </>}
            {state.result.payment.period_end && <>valid until {formatDate(state.result.payment.period_end)} · </>}
            receipt {state.result.payment.receipt_number}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href={state.result.membership ? `/student/memberships/${state.result.membership.id}` : "/student/memberships"}>
                Go to my membership
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href={`/student/payments/${state.result.payment.id}`}>View receipt</Link>
            </Button>
          </div>
        </div>
      );
    default:
      return null;
  }
}
