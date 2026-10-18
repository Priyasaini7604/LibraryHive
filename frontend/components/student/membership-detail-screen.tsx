"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Breadcrumbs } from "@/components/ui/navigation";
import { Fact, LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { METHOD_LABEL, MembershipBadge } from "@/components/ui/status-badges";
import { Card, CardContent } from "@/components/ui/surface";
import { fetchStudentMembership } from "@/lib/api/memberships";
import { isApiError } from "@/lib/errors";
import { formatDate, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { PaymentPeriod } from "@/lib/types";

/** `/student/memberships/[id]`: the membership card with its period history (#57). */
export function MembershipDetailScreen({ id }: { id: string }) {
  const query = useQuery({ queryKey: queryKeys.studentMembership(id), queryFn: () => fetchStudentMembership(id) });

  if (query.isPending) {
    return (
      <Page>
        <LoadingList label="Loading your membership" />
      </Page>
    );
  }
  if (query.isError) {
    return (
      <Page>
        {isApiError(query.error, "NOT_FOUND") ? (
          <EmptyState
            title="We couldn't find this membership"
            action={
              <Button asChild variant="secondary">
                <Link href="/student/memberships">My membership</Link>
              </Button>
            }
          />
        ) : (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your membership." />
        )}
      </Page>
    );
  }

  const m = query.data;
  return (
    <Page>
      <Breadcrumbs items={[{ label: "My membership", href: "/student/memberships" }, { label: m.library.name }]} />
      <PageHeader
        title={m.library.name}
        description={`Seat ${m.seat.label} · ${m.plan.name}`}
        actions={
          <>
            {m.renewal_open && (
              <Button asChild>
                <Link href={`/student/memberships/${m.id}/renew`}>Renew</Link>
              </Button>
            )}
            <Button asChild variant="secondary">
              <Link href={`/libraries/${m.library.id}`}>Library page</Link>
            </Button>
          </>
        }
      />
      <Card aria-label="Membership summary">
        <CardContent className="pt-4">
          <dl className="grid gap-4 sm:grid-cols-4">
            <Fact label="Status">
              <MembershipBadge status={m.status} />
            </Fact>
            <Fact label="Started">{formatDate(m.start_date)}</Fact>
            <Fact label={m.status === "archived" ? "Ended" : "Valid until"}>{formatDate(m.next_due_date)}</Fact>
            <Fact label="Plan">
              {m.plan.name} · {formatMoney(m.plan.price)}
            </Fact>
          </dl>
        </CardContent>
      </Card>

      <section aria-labelledby="history-heading" className="flex flex-col gap-3">
        <h2 id="history-heading" className="text-lg font-semibold text-slate-900">
          Payment history
        </h2>
        {m.payments.length === 0 ? (
          <EmptyState title="No payments yet" />
        ) : (
          <DataTable<PaymentPeriod>
            caption="Payments for this membership"
            rows={m.payments}
            rowKey={(row) => row.id}
            columns={[
              {
                key: "period",
                header: "Period",
                primary: true,
                cell: (row) => (row.period_start && row.period_end ? `${formatDate(row.period_start)} – ${formatDate(row.period_end)}` : "—"),
              },
              { key: "amount", header: "Amount", cell: (row) => formatMoney(row.amount) },
              { key: "method", header: "Paid by", cell: (row) => METHOD_LABEL[row.method] },
              { key: "receipt", header: "Receipt", cell: (row) => row.receipt_number },
            ]}
            rowActions={(row) => (
              <Button asChild size="sm" variant="secondary">
                <Link href={`/student/payments/${row.id}`} aria-label={`Receipt ${row.receipt_number}`}>
                  Receipt
                </Link>
              </Button>
            )}
          />
        )}
      </section>
    </Page>
  );
}
