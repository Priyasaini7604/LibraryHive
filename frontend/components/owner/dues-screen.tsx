"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { RecordRenewalDialog } from "@/components/owner/record-renewal-dialog";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { DataTable, FilterBar } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { Pagination } from "@/components/ui/navigation";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Badge } from "@/components/ui/surface";
import { fetchDues } from "@/lib/api/memberships";
import { formatDate, formatMoney, formatPhone } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { DueRow } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "any", label: "Due and overdue" },
  { value: "due", label: "Due soon" },
  { value: "overdue", label: "Overdue" },
];
const BUCKET_OPTIONS = [
  { value: "any", label: "Any lateness" },
  { value: "1-7", label: "1–7 days late" },
  { value: "8-15", label: "8–15 days late" },
  { value: "15+", label: "More than 15 days late" },
];

/** `/owner/dues`: who owes a renewal, most overdue first (#49). Recording a payment renews the member (#48). */
export function DuesScreen() {
  const [status, setStatus] = useState("any");
  const [bucket, setBucket] = useState("any");
  const [page, setPage] = useState(1);
  const [paying, setPaying] = useState<DueRow | null>(null);

  const filters = {
    status: status === "any" ? undefined : (status as "due" | "overdue"),
    bucket: bucket === "any" ? undefined : (bucket as "1-7" | "8-15" | "15+"),
    page,
  };
  const query = useQuery({ queryKey: queryKeys.ownerDues(filters), queryFn: () => fetchDues(filters), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader title="Dues" description="Members whose renewal is due soon or late. Record a payment when they pay you." />
      <FilterBar label="Filter dues">
        <FormField label="Show" className="sm:w-52">
          <Select value={status} onValueChange={(value) => { setStatus(value); setPage(1); }} options={STATUS_OPTIONS} />
        </FormField>
        <FormField label="How late" className="sm:w-60">
          <Select value={bucket} onValueChange={(value) => { setBucket(value); setPage(1); }} options={BUCKET_OPTIONS} />
        </FormField>
      </FilterBar>

      {query.isPending ? (
        <LoadingList label="Loading dues" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your dues." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="Nothing is due" description="Every member is paid up for now." />
      ) : (
        <>
          <DataTable<DueRow>
            caption="Dues"
            rows={query.data.items}
            rowKey={(row) => row.membership_id}
            columns={[
              {
                key: "name",
                header: "Member",
                primary: true,
                cell: (row) => (
                  <Link href={`/owner/members/${row.membership_id}`} className="font-medium text-blue-700 hover:underline">
                    {row.student.name}
                  </Link>
                ),
              },
              { key: "phone", header: "Phone", cell: (row) => formatPhone(row.student.phone) },
              { key: "seat", header: "Seat", cell: (row) => row.seat_label },
              { key: "due", header: "Due on", cell: (row) => formatDate(row.next_due_date) },
              {
                key: "late",
                header: "Status",
                cell: (row) =>
                  row.status === "overdue" ? (
                    <Badge tone="danger">{row.days_overdue} day{row.days_overdue === 1 ? "" : "s"} overdue</Badge>
                  ) : (
                    <Badge tone="warning">Due soon</Badge>
                  ),
              },
              { key: "amount", header: "Amount due", cell: (row) => formatMoney(row.amount_due) },
            ]}
            rowActions={(row) => (
              <Button size="sm" variant="secondary" aria-label={`Record payment for ${row.student.name}`} onClick={() => setPaying(row)}>
                Record payment
              </Button>
            )}
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}

      {paying && <RecordRenewalDialog membershipId={paying.membership_id} studentName={paying.student.name} currentPlanId={paying.plan.id} onClose={() => setPaying(null)} />}
    </Page>
  );
}
