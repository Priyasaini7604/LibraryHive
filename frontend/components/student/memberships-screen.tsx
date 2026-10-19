"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/choice";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { MembershipBadge } from "@/components/ui/status-badges";
import { Card, CardContent } from "@/components/ui/surface";
import { fetchStudentMemberships } from "@/lib/api/memberships";
import { formatDate, formatMoney, relativeDue, businessDate } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { StudentMembership } from "@/lib/types";

export function MembershipCard({ membership }: { membership: StudentMembership }) {
  const archived = membership.status === "archived";
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-4">
        <div className="flex flex-col gap-1">
          <p className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
            {membership.library.name}
            <MembershipBadge status={membership.status} />
          </p>
          <p className="text-sm text-slate-700">
            Seat {membership.seat.label} · {membership.plan.name} · {formatMoney(membership.plan.price)} for {membership.plan.duration_days} days
          </p>
          <p className="text-sm text-slate-700">
            {archived
              ? `Ended · started ${formatDate(membership.start_date)}`
              : `Valid until ${formatDate(membership.next_due_date)} (${relativeDue(membership.next_due_date, businessDate())})`}
          </p>
        </div>
        <div className="flex gap-2">
          {membership.renewal_open && (
            <Button asChild size="sm">
              <Link href={`/student/memberships/${membership.id}/renew`}>Renew</Link>
            </Button>
          )}
          <Button asChild size="sm" variant="secondary">
            <Link href={`/student/memberships/${membership.id}`} aria-label={`Details of your membership at ${membership.library.name}`}>
              Details
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/** `/student/memberships`: the student's own memberships (#56). */
export function MembershipsScreen() {
  const [includeArchived, setIncludeArchived] = useState(false);
  const query = useQuery({ queryKey: queryKeys.studentMemberships(includeArchived), queryFn: () => fetchStudentMemberships(includeArchived) });

  return (
    <Page>
      <PageHeader title="My membership" description="Your seats, due dates and renewals." />
      <Checkbox label="Show past memberships" checked={includeArchived} onCheckedChange={(value) => setIncludeArchived(value === true)} />
      {query.isPending ? (
        <LoadingList label="Loading your memberships" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your memberships." />
      ) : query.data.length === 0 ? (
        <EmptyState
          title={includeArchived ? "No memberships yet" : "You don't have a seat yet"}
          description="Find a library near you and book a seat."
          action={
            <Button asChild>
              <Link href="/discover">Find a library</Link>
            </Button>
          }
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {query.data.map((membership) => (
            <li key={membership.id}>
              <MembershipCard membership={membership} />
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
