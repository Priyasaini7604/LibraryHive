"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PaymentOutcome } from "@/components/booking/payment-outcome";
import { usePaymentFlow } from "@/components/booking/use-payment-flow";
import { useLeaveWarning } from "@/components/booking/checkout-screen";
import { Button } from "@/components/ui/button";
import { RadioCardGroup } from "@/components/ui/choice";
import { Page, PageHeader } from "@/components/ui/page";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Card, CardContent } from "@/components/ui/surface";
import { fetchLibrary } from "@/lib/api/libraries";
import { fetchStudentMembership } from "@/lib/api/memberships";
import { addDays, businessDate, formatDate, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const RESTART_AFTER_OVERDUE_DAYS = 15;

/** Decision D5: the new period starts at the old due date, or today once more than 15 days overdue. */
export function renewalStart(nextDueDate: string, today: string): string {
  const overdue = (Date.parse(`${today}T00:00:00Z`) - Date.parse(`${nextDueDate}T00:00:00Z`)) / 86_400_000;
  return overdue > RESTART_AFTER_OVERDUE_DAYS ? today : nextDueDate;
}

/** `/student/memberships/[id]/renew`: renew with the same plan or choose another of the same library (T18). */
export function RenewalScreen({ membershipId }: { membershipId: string }) {
  const queryClient = useQueryClient();
  const membership = useQuery({ queryKey: queryKeys.studentMembership(membershipId), queryFn: () => fetchStudentMembership(membershipId) });
  const libraryId = membership.data?.library.id;
  const library = useQuery({
    queryKey: queryKeys.library(libraryId ?? ""),
    queryFn: ({ signal }) => fetchLibrary(libraryId as string, signal),
    enabled: Boolean(libraryId),
  });
  const [chosen, setChosen] = useState<string | null>(null);
  const planId = chosen ?? membership.data?.plan.id ?? null;
  const source = useMemo(
    () => ({ membership: membershipId, plan: planId && planId !== membership.data?.plan.id ? planId : undefined }),
    [membershipId, planId, membership.data?.plan.id],
  );
  const flow = usePaymentFlow(source, () => void queryClient.invalidateQueries({ queryKey: ["student"] }));
  const { state } = flow;
  useLeaveWarning(state.kind === "awaiting_payment" || state.kind === "verifying" || state.kind === "confirming_slow");

  if (membership.isPending || (Boolean(libraryId) && library.isPending)) {
    return (
      <Page className="max-w-2xl">
        <div aria-busy="true" className="flex flex-col gap-3">
          <span className="sr-only" role="status">
            Loading
          </span>
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-40 w-full" />
        </div>
      </Page>
    );
  }
  if (membership.isError) {
    return (
      <Page className="max-w-2xl">
        <ErrorState error={membership.error} onRetry={() => void membership.refetch()} title="We couldn't load your membership." />
      </Page>
    );
  }

  const current = membership.data;
  const plans = library.data?.plans ?? [];
  const plan = plans.find((item) => item.id === planId) ?? { id: current.plan.id, name: current.plan.name, price: current.plan.price, duration_days: current.plan.duration_days, timing_note: "" };
  const start = renewalStart(current.next_due_date, businessDate());
  const until = addDays(start, plan.duration_days);
  const finished = ["success", "seat_lost", "confirming_slow", "confirm_timeout"].includes(state.kind);
  const payable = ["ready", "dismissed", "failed"].includes(state.kind);

  if (current.status === "archived") {
    return (
      <Page className="max-w-2xl">
        <PageHeader title="Renew your membership" />
        <Alert tone="info">This membership has ended. Book a seat again from the library page.</Alert>
        <Button asChild variant="secondary" className="self-start">
          <Link href={`/libraries/${current.library.id}`}>Go to the library</Link>
        </Button>
      </Page>
    );
  }

  return (
    <Page className="max-w-2xl">
      <PageHeader title="Renew your membership" description={`${current.library.name} · seat ${current.seat.label}`} />

      {!current.renewal_open && !finished && (
        <Alert tone="info" title="Renewal isn't open yet">
          You can renew from 7 days before your due date ({formatDate(current.next_due_date)}).
        </Alert>
      )}

      {!finished && plans.length > 1 && (
        <RadioCardGroup
          label="Plan for the next period"
          value={planId ?? undefined}
          onValueChange={setChosen}
          options={plans.map((item) => ({
            value: item.id,
            title: item.name,
            description: `${formatMoney(item.price)} for ${item.duration_days} days`,
          }))}
        />
      )}

      <Card aria-label="Renewal summary">
        <CardContent className="flex flex-col gap-1 pt-4">
          <p className="text-slate-700">
            Current due date: <strong>{formatDate(current.next_due_date)}</strong>
          </p>
          <p className="text-slate-700">
            New period: {formatDate(start)} – <strong>{formatDate(until)}</strong>
          </p>
          <p className="mt-2 flex items-baseline justify-between border-t border-slate-200 pt-3">
            <span className="text-slate-700">Total</span>
            <span className="text-xl font-semibold text-slate-900">{formatMoney(plan.price)}</span>
          </p>
        </CardContent>
      </Card>

      {state.kind === "dismissed" && <Alert tone="warning" title="Payment not completed">You closed the payment window. You can try again.</Alert>}
      {state.kind === "failed" && <Alert tone="danger" title="The payment didn't go through">{state.message}</Alert>}

      <PaymentOutcome state={state} seatLabel={current.seat.label} libraryHref={`/libraries/${current.library.id}`} successTitle="Your membership is renewed" />

      {payable && (
        <Button size="lg" className="self-start" disabled={!current.renewal_open} onClick={() => void flow.start()}>
          {state.kind === "ready" ? `Pay ${formatMoney(plan.price)}` : "Try again"}
        </Button>
      )}
    </Page>
  );
}
