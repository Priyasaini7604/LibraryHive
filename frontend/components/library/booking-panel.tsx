"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { SeatLegend, SeatMap, type MapSeat } from "@/components/seat-map/seat-map";
import { Button } from "@/components/ui/button";
import { RadioCardGroup } from "@/components/ui/choice";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Alert } from "@/components/ui/surface";
import { createHold, fetchPublicSeats } from "@/lib/api/seats";
import { useAuth } from "@/lib/auth-context";
import { isApiError, userMessage } from "@/lib/errors";
import { formatMoney } from "@/lib/format";
import { loginUrl } from "@/lib/navigation";
import { queryKeys } from "@/lib/query-keys";
import type { PricingPlan } from "@/lib/types";

function initialParam(name: string): string | null {
  return typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get(name);
}

/**
 * Seat map and booking start on the public library page (UI_ARCHITECTURE.md 5.2). Picking a free seat and a
 * plan holds the seat for a few minutes (#38) and continues to checkout. The choice survives a login round trip
 * through the `seat` and `plan` query parameters.
 */
export function BookingPanel({ libraryId, plans }: { libraryId: string; plans: PricingPlan[] }) {
  const { status, user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [seatId, setSeatId] = useState<string | null>(() => initialParam("seat"));
  const [planId, setPlanId] = useState<string | null>(() => initialParam("plan") ?? (plans.length === 1 ? (plans[0]?.id ?? null) : null));
  const [problem, setProblem] = useState<{ message: string; resume: boolean } | null>(null);

  const seats = useQuery({
    queryKey: queryKeys.publicSeats(libraryId),
    queryFn: ({ signal }) => fetchPublicSeats(libraryId, signal),
    refetchInterval: 30_000,
  });

  const hold = useMutation({
    mutationFn: () => createHold({ seat_id: seatId as string, plan_id: planId as string }),
    onSuccess: (created) => router.push(`/student/book/${created.id}`),
    onError: (error) => {
      setProblem({ message: userMessage(error), resume: isApiError(error, "HOLD_EXISTS") });
      if (isApiError(error, "SEAT_UNAVAILABLE")) {
        setSeatId(null);
        toast.error(userMessage(error));
        void queryClient.invalidateQueries({ queryKey: queryKeys.publicSeats(libraryId) });
      }
    },
  });

  if (seats.isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-2">
        <span className="sr-only" role="status">
          Loading seats
        </span>
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-3/4" />
      </div>
    );
  }
  if (seats.isError) return <ErrorState error={seats.error} onRetry={() => void seats.refetch()} title="We couldn't load the seats." />;
  if (seats.data.seats.length === 0) {
    return <EmptyState title="No seats listed yet" description="This library hasn't added its seats." />;
  }

  const { seats: list, counts } = seats.data;
  const selected = list.find((seat) => seat.id === seatId) ?? null;
  const plan = plans.find((item) => item.id === planId) ?? null;
  const choice = selected && plan ? `?seat=${selected.id}&plan=${plan.id}` : "";
  const nextAfterLogin = `/libraries/${libraryId}${choice}`;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-slate-700">
        {counts.empty} free · {counts.reserved} reserved · {counts.occupied} taken · {counts.total} in total
      </p>
      <SeatLegend />
      <SeatMap
        label="Seat map. Choose a free seat."
        seats={list as MapSeat[]}
        selectedId={selected?.id ?? null}
        onSelect={(seat) => {
          setSeatId(seat.id);
          setProblem(null);
        }}
      />

      {plans.length > 0 && (
        <RadioCardGroup
          label="Choose a plan"
          value={planId ?? undefined}
          onValueChange={(value) => setPlanId(value)}
          options={plans.map((item) => ({
            value: item.id,
            title: item.name,
            description: `${formatMoney(item.price)} for ${item.duration_days} days`,
          }))}
        />
      )}

      {problem && (
        <Alert
          tone="danger"
          action={
            problem.resume ? (
              <Button asChild variant="secondary" size="sm">
                <Link href="/student">Continue your booking</Link>
              </Button>
            ) : undefined
          }
        >
          {problem.message}
        </Alert>
      )}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {status === "anonymous" ? (
          <Button asChild disabled={!selected || !plan}>
            <Link href={loginUrl(nextAfterLogin)}>Log in to book {selected ? `seat ${selected.label}` : "a seat"}</Link>
          </Button>
        ) : user?.role === "owner" ? (
          <Alert tone="info">Library owners can&apos;t book seats. Sign in with a student account to book.</Alert>
        ) : (
          <Button disabled={!selected || !plan || status === "loading"} loading={hold.isPending} onClick={() => hold.mutate()}>
            {selected ? `Hold seat ${selected.label}` : "Choose a seat"}
          </Button>
        )}
        {selected && plan && (
          <p className="text-sm text-slate-700">
            Seat {selected.label} · {plan.name} · {formatMoney(plan.price)}. The seat is held for a few minutes while you pay.
          </p>
        )}
      </div>
    </div>
  );
}
