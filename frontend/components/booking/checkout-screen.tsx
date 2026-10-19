"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { HoldCountdown } from "@/components/booking/hold-countdown";
import { PaymentOutcome } from "@/components/booking/payment-outcome";
import { usePaymentFlow } from "@/components/booking/use-payment-flow";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Page, PageHeader } from "@/components/ui/page";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Card, CardContent } from "@/components/ui/surface";
import { serverNow } from "@/lib/api-client";
import { cancelHold, fetchCurrentHolds } from "@/lib/api/seats";
import { userMessage } from "@/lib/errors";
import { addDays, businessDate, formatDate, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

/** Warn before leaving while a payment is in flight (UI_ARCHITECTURE.md 5.3). */
export function useLeaveWarning(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [active]);
}

/** `/student/book/[holdId]`: summary, countdown and the pay button for a held seat (T18). */
export function CheckoutScreen({ holdId }: { holdId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const holds = useQuery({ queryKey: queryKeys.currentHolds, queryFn: fetchCurrentHolds });

  const source = useMemo(() => ({ hold: holdId }), [holdId]);
  const flow = usePaymentFlow(source, () => {
    void queryClient.invalidateQueries({ queryKey: ["student"] });
  });
  const { state } = flow;
  useLeaveWarning(state.kind === "awaiting_payment" || state.kind === "verifying" || state.kind === "confirming_slow");

  const hold = holds.data?.find((item) => item.id === holdId) ?? null;
  const libraryHref = hold ? `/libraries/${hold.library.id}` : "/discover";

  const cancel = useMutation({
    mutationFn: () => cancelHold(holdId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.currentHolds });
      toast.success("Booking cancelled. The seat is free again.");
      router.push(libraryHref);
    },
    onError: (error) => {
      setConfirmingCancel(false);
      toast.error(userMessage(error));
      void holds.refetch();
    },
  });

  const refreshHold = useCallback(() => void holds.refetch(), [holds]);

  if (holds.isPending) {
    return (
      <Page className="max-w-2xl">
        <div aria-busy="true" className="flex flex-col gap-3">
          <span className="sr-only" role="status">
            Loading your booking
          </span>
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-40 w-full" />
        </div>
      </Page>
    );
  }
  if (holds.isError) {
    return (
      <Page className="max-w-2xl">
        <ErrorState error={holds.error} onRetry={() => void holds.refetch()} title="We couldn't load your booking." />
      </Page>
    );
  }

  const finished = ["success", "seat_lost", "confirming_slow", "confirm_timeout"].includes(state.kind);
  const payable = ["ready", "dismissed", "failed"].includes(state.kind);

  // The server decides whether the hold is still live: once it is gone the page shows "expired".
  if (!hold && !finished) {
    return (
      <Page className="max-w-2xl">
        <PageHeader title="Complete your booking" />
        <PaymentOutcome state={{ kind: "expired" }} libraryHref={libraryHref} successTitle="" />
      </Page>
    );
  }

  const validUntil = hold ? addDays(businessDate(serverNow()), hold.plan.duration_days) : null;

  return (
    <Page className="max-w-2xl">
      <PageHeader
        title="Complete your booking"
        actions={
          hold &&
          !finished && (
            <HoldCountdown
              expiresAt={hold.expires_at}
              paused={state.kind === "awaiting_payment" || state.kind === "verifying"}
              onElapsed={refreshHold}
            />
          )
        }
      />

      {hold && (
        <Card aria-label="Booking summary">
          <CardContent className="flex flex-col gap-1 pt-4">
            <p className="text-lg font-semibold text-slate-900">{hold.library.name}</p>
            <p className="text-slate-700">
              Seat {hold.seat.label} · {hold.plan.name} plan
            </p>
            {validUntil && <p className="text-slate-700">Valid until {formatDate(validUntil)}</p>}
            <p className="mt-2 flex items-baseline justify-between border-t border-slate-200 pt-3">
              <span className="text-slate-700">Total</span>
              <span className="text-xl font-semibold text-slate-900">{formatMoney(hold.amount)}</span>
            </p>
          </CardContent>
        </Card>
      )}

      {state.kind === "dismissed" && <Alert tone="warning" title="Payment not completed">You closed the payment window. Your seat is still held; you can try again.</Alert>}
      {state.kind === "failed" && <Alert tone="danger" title="The payment didn't go through">{state.message}</Alert>}

      <PaymentOutcome state={state} seatLabel={hold?.seat.label} libraryHref={libraryHref} successTitle="Your seat is booked" />

      {hold && payable && (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="lg" onClick={() => void flow.start()}>
            {state.kind === "ready" ? `Pay ${formatMoney(hold.amount)}` : "Try again"}
          </Button>
          <Button variant="secondary" onClick={() => setConfirmingCancel(true)}>
            Cancel booking
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={confirmingCancel}
        onOpenChange={setConfirmingCancel}
        title="Cancel this booking?"
        description="The seat is released straight away and anyone can book it."
        confirmLabel="Cancel booking"
        destructive
        loading={cancel.isPending}
        onConfirm={() => cancel.mutate()}
      />
    </Page>
  );
}
