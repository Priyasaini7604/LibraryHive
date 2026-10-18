"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { DomainBars, OccupancyBar } from "@/components/charts/bars";
import { StatCard } from "@/components/charts/stat-card";
import { Button } from "@/components/ui/button";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { ErrorState } from "@/components/ui/states";
import { METHOD_LABEL } from "@/components/ui/status-badges";
import { Alert, Card, CardContent, CardHeader, CardTitle } from "@/components/ui/surface";
import { fetchOwnerDashboard } from "@/lib/api/operations";
import { formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { PaymentMethod } from "@/lib/types";

/** `/owner`: KPIs from the same selectors as the lists they link to (#82, T23, DASH-01/02/03/08). */
const CHECKLIST_LABELS: Record<string, string> = {
  has_profile: "library profile",
  has_location: "location",
  has_active_plan: "an active plan",
  has_active_seat: "an active seat",
};

export function OwnerDashboardScreen() {
  const query = useQuery({ queryKey: queryKeys.ownerDashboard, queryFn: fetchOwnerDashboard, refetchInterval: 60_000 });
  const missing = Object.entries(query.data?.publish_checklist ?? {})
    .filter(([, done]) => !done)
    .map(([key]) => CHECKLIST_LABELS[key] ?? key);

  return (
    <Page>
      <PageHeader title="Dashboard" description="How your library is doing today." />
      {query.isPending ? (
        <LoadingList label="Loading your dashboard" rows={4} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your dashboard." />
      ) : (
        <>
          {missing.length > 0 && (
            <Alert
              tone="warning"
              title="Your library isn't visible to students yet"
              action={
                <Button asChild size="sm">
                  <Link href="/owner/library">Finish setup</Link>
                </Button>
              }
            >
              Still to do: {missing.join(", ")}.
            </Alert>
          )}

          <section aria-labelledby="seats-heading" className="flex flex-col gap-3">
            <h2 id="seats-heading" className="text-lg font-semibold text-slate-900">
              Seats
            </h2>
            {query.data.seats.total === 0 ? (
              <Alert tone="info" action={<Button asChild size="sm"><Link href="/owner/seats">Add seats</Link></Button>}>
                You haven&apos;t added any seats yet.
              </Alert>
            ) : (
              <OccupancyBar label="Seat occupancy" {...query.data.seats} />
            )}
          </section>

          <section aria-labelledby="people-heading" className="flex flex-col gap-3">
            <h2 id="people-heading" className="text-lg font-semibold text-slate-900">
              Members
            </h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <StatCard label="Active members" value={query.data.members.active} href="/owner/members" />
              <StatCard label="Due soon" value={query.data.members.due} tone={query.data.members.due ? "warning" : "neutral"} href="/owner/dues" />
              <StatCard label="Overdue" value={query.data.members.overdue} tone={query.data.members.overdue ? "danger" : "neutral"} href="/owner/dues" />
            </div>
          </section>

          <section aria-labelledby="today-heading" className="flex flex-col gap-3">
            <h2 id="today-heading" className="text-lg font-semibold text-slate-900">
              Today
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="New bookings" value={query.data.today.new_bookings} href="/owner/members" />
              <StatCard label="Check-ins" value={query.data.today.check_ins} href="/owner/attendance" />
              <StatCard label="In the library now" value={query.data.today.present_now} href="/owner/attendance" />
              <StatCard label="Renewals in 7 days" value={query.data.upcoming_renewals_7d} href="/owner/members" />
            </div>
          </section>

          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Revenue this month" value={formatMoney(query.data.revenue.this_month_total)} href="/owner/payments" />
            <StatCard label="Open complaints" value={query.data.open_complaints} tone={query.data.open_complaints ? "warning" : "neutral"} href="/owner/complaints" />
            <StatCard label="Visit requests waiting" value={query.data.pending_visits} tone={query.data.pending_visits ? "warning" : "neutral"} href="/owner/visits" />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Revenue by method</CardTitle>
              </CardHeader>
              <CardContent>
                {Object.keys(query.data.revenue.by_method).length === 0 ? (
                  <p className="text-sm text-slate-600">No payments this month.</p>
                ) : (
                  <ul className="flex flex-col gap-1 text-sm">
                    {Object.entries(query.data.revenue.by_method).map(([method, bucket]) => (
                      <li key={method} className="flex justify-between">
                        <span>{METHOD_LABEL[method as PaymentMethod] ?? method}</span>
                        <span className="tabular-nums">
                          {formatMoney(bucket.total)} · {bucket.count}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Members by exam</CardTitle>
              </CardHeader>
              <CardContent>
                {query.data.domain_breakdown.length === 0 ? (
                  <p className="text-sm text-slate-600">Members haven&apos;t chosen an exam yet.</p>
                ) : (
                  <DomainBars rows={query.data.domain_breakdown} />
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </Page>
  );
}
