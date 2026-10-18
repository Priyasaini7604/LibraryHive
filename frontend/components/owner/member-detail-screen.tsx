"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ClaimCodeDialog } from "@/components/owner/claim-code-dialog";
import { RecordRenewalDialog } from "@/components/owner/record-renewal-dialog";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Breadcrumbs } from "@/components/ui/navigation";
import { Fact, LoadingList, Page, PageHeader } from "@/components/ui/page";
import { ReasonDialog } from "@/components/ui/reason-dialog";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { METHOD_LABEL, MembershipBadge } from "@/components/ui/status-badges";
import { Badge, Card, CardContent } from "@/components/ui/surface";
import { archiveMember, fetchMember } from "@/lib/api/memberships";
import { isApiError, userMessage } from "@/lib/errors";
import { formatDate, formatDateTime, formatMoney, formatPhone } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { PaymentPeriod } from "@/lib/types";

/** `/owner/members/[id]`: one member, their period history, and the renew and archive actions (#51, #48, #52). */
export function MemberDetailScreen({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [renewing, setRenewing] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const query = useQuery({ queryKey: queryKeys.ownerMember(id), queryFn: () => fetchMember(id) });

  const archive = useMutation({
    mutationFn: (reason: string) => archiveMember(id, reason),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["owner"] });
      toast.success("Member archived. The seat is free.");
      setArchiving(false);
    },
    onError: (error) => setArchiveError(userMessage(error)),
  });

  if (query.isPending) {
    return (
      <Page>
        <LoadingList label="Loading the member" />
      </Page>
    );
  }
  if (query.isError) {
    return (
      <Page>
        {isApiError(query.error, "NOT_FOUND") ? (
          <EmptyState
            title="We couldn't find this member"
            action={
              <Button asChild variant="secondary">
                <Link href="/owner/members">Members</Link>
              </Button>
            }
          />
        ) : (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load this member." />
        )}
      </Page>
    );
  }

  const m = query.data;
  const ended = m.status === "archived";
  return (
    <Page>
      <Breadcrumbs items={[{ label: "Members", href: "/owner/members" }, { label: m.student.name }]} />
      <PageHeader
        title={m.student.name}
        description={`Seat ${m.seat.label} · ${m.plan.name}`}
        actions={
          !ended && (
            <>
              <Button onClick={() => setRenewing(true)}>Record a renewal</Button>
              <Button variant="danger" onClick={() => setArchiving(true)}>
                Archive member
              </Button>
            </>
          )
        }
      />

      <Card aria-label="Member summary">
        <CardContent className="pt-4">
          <dl className="grid gap-4 sm:grid-cols-3">
            <Fact label="Status">
              <MembershipBadge status={m.status} />
            </Fact>
            <Fact label={ended ? "Ended" : "Valid until"}>{formatDate(ended && m.archived_at ? m.archived_at.slice(0, 10) : m.next_due_date)}</Fact>
            <Fact label="Started">{formatDate(m.start_date)}</Fact>
            <Fact label="Phone">{formatPhone(m.student.phone)}</Fact>
            <Fact label="Email">{m.student.email ?? "—"}</Fact>
            <Fact label="Exam">{m.student.domain ?? "—"}</Fact>
            <Fact label="Source">{m.source === "offline" ? "Added by you" : "Booked online"}</Fact>
            <Fact label="Days present this month">{m.attendance_summary.this_month_days}</Fact>
            <Fact label="Last check-in">{m.attendance_summary.last_check_in ? formatDateTime(m.attendance_summary.last_check_in) : "Never"}</Fact>
            <Fact label="Complaints raised">
              {m.complaints_count > 0 ? <Link href="/owner/complaints" className="text-blue-700 hover:underline">{m.complaints_count}</Link> : 0}
            </Fact>
            {m.student.is_offline && (
              <Fact label="Account">
                <span className="flex flex-wrap items-center gap-2">
                  <Badge>Not signed up yet</Badge>
                  <Button size="sm" variant="secondary" onClick={() => setClaiming(true)}>
                    Give a claim code
                  </Button>
                </span>
              </Fact>
            )}
            {ended && m.archive_reason && <Fact label="Reason for ending">{m.archive_reason}</Fact>}
          </dl>
        </CardContent>
      </Card>

      <section aria-labelledby="period-heading" className="flex flex-col gap-3">
        <h2 id="period-heading" className="text-lg font-semibold text-slate-900">
          Payment history
        </h2>
        {m.payments.length === 0 ? (
          <EmptyState title="No payments recorded" />
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
          />
        )}
      </section>

      {m.other_memberships_here.length > 0 && (
        <section aria-labelledby="tenure-heading" className="flex flex-col gap-3">
          <h2 id="tenure-heading" className="text-lg font-semibold text-slate-900">
            Earlier memberships here
          </h2>
          <ul className="flex flex-col gap-2">
            {m.other_memberships_here.map((other) => (
              <li key={other.membership_id} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
                <MembershipBadge status={other.status} />
                <span>
                  Seat {other.seat.label} · {formatDate(other.start_date)} – {formatDate(other.next_due_date)}
                </span>
                <Link href={`/owner/members/${other.membership_id}`} className="ml-auto text-blue-700 hover:underline">
                  View
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {claiming && <ClaimCodeDialog studentId={m.student.id} studentName={m.student.name} onClose={() => setClaiming(false)} />}
      {renewing && <RecordRenewalDialog membershipId={m.membership_id} studentName={m.student.name} currentPlanId={m.plan.id} onClose={() => setRenewing(false)} />}
      <ReasonDialog
        open={archiving}
        onOpenChange={(open) => {
          setArchiving(open);
          if (!open) setArchiveError(null);
        }}
        title={`Archive ${m.student.name}?`}
        description="The member's seat becomes free straight away. Their payments and attendance stay in your records. Archived members can be admitted again later as a new membership."
        confirmLabel="Archive member"
        destructive
        maxLength={300}
        loading={archive.isPending}
        error={archiveError}
        onSubmit={(reason) => archive.mutate(reason)}
      />
    </Page>
  );
}
