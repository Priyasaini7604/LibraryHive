"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { CheckInCard } from "@/components/attendance/check-in-card";
import { MembershipCard } from "@/components/student/memberships-screen";
import { StatCard } from "@/components/charts/stat-card";
import { Button } from "@/components/ui/button";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { PaymentBadge, SLOT_LABEL, VisitBadge } from "@/components/ui/status-badges";
import { Alert } from "@/components/ui/surface";
import { fetchStudentDashboard } from "@/lib/api/operations";
import { useAuth } from "@/lib/auth-context";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

/** `/student`: the student's home (#89): booking in progress, membership, check-in, payments, requests. */
export function StudentDashboardScreen() {
  const { user } = useAuth();
  const query = useQuery({ queryKey: queryKeys.studentDashboard, queryFn: fetchStudentDashboard });

  return (
    <Page>
      <PageHeader title={user ? `Hello, ${user.name.split(" ")[0]}` : "Home"} description="Your seat, payments and requests in one place." />
      {query.isPending ? (
        <LoadingList label="Loading your home" rows={4} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your home page." />
      ) : (
        <>
          {query.data.pending_hold && (
            <Alert
              tone="warning"
              title="You have a seat on hold"
              action={
                <Button asChild size="sm">
                  <Link href={`/student/book/${query.data.pending_hold.id}`}>Continue your booking</Link>
                </Button>
              }
            >
              Seat {query.data.pending_hold.seat_label} at {query.data.pending_hold.library.name} is held until {formatDateTime(query.data.pending_hold.expires_at)}.
            </Alert>
          )}

          <section aria-labelledby="membership-heading" className="flex flex-col gap-3">
            <h2 id="membership-heading" className="text-lg font-semibold text-slate-900">
              My membership
            </h2>
            {query.data.memberships.length === 0 ? (
              <EmptyState
                title="You don't have a seat yet"
                description="Find a library near you, pick a seat and pay online."
                action={
                  <Button asChild>
                    <Link href="/discover">Find a library</Link>
                  </Button>
                }
              />
            ) : (
              <ul className="flex flex-col gap-3">
                {query.data.memberships.map((membership) => (
                  <li key={membership.id}>
                    <MembershipCard membership={membership} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          {query.data.memberships.length > 0 && <CheckInCard />}

          <div className="grid gap-3 sm:grid-cols-2">
            <StatCard label="Open complaints" value={query.data.open_complaints} href="/student/complaints" />
            <StatCard label="Visit requests" value={query.data.visits.length} hint="Waiting or coming up" href="/student/visits" />
          </div>

          {query.data.visits.length > 0 && (
            <section aria-labelledby="visits-heading" className="flex flex-col gap-2">
              <h2 id="visits-heading" className="text-lg font-semibold text-slate-900">
                Upcoming visits
              </h2>
              <ul className="flex flex-col gap-2">
                {query.data.visits.map((visit) => (
                  <li key={visit.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
                    <VisitBadge status={visit.status} />
                    <span>
                      {visit.library.name} · {formatDate(visit.preferred_date)} · {SLOT_LABEL[visit.preferred_slot]}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="recent-heading" className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <h2 id="recent-heading" className="text-lg font-semibold text-slate-900">
                Recent payments
              </h2>
              <Link href="/student/payments" className="text-sm font-medium text-blue-700 hover:underline">
                All payments
              </Link>
            </div>
            {query.data.recent_payments.length === 0 ? (
              <p className="text-sm text-slate-600">No payments yet.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {query.data.recent_payments.map((payment) => (
                  <li key={payment.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm">
                    <PaymentBadge status={payment.status} />
                    <span>
                      {formatMoney(payment.amount)} · {payment.library.name} · {formatDateTime(payment.paid_at ?? payment.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </Page>
  );
}
