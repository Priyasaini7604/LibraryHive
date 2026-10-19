"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterBar } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { DateField, Input } from "@/components/ui/input";
import { Breadcrumbs, Pagination } from "@/components/ui/navigation";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { fetchAuditLog } from "@/lib/api/operations";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { AuditEntry } from "@/lib/types";

/** "membership.renew" -> "Membership renew": a readable action name; the raw name stays in the title. */
function actionLabel(action: string): string {
  const text = action.replace(/[._]/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** `/owner/activity`: who changed what in the library, newest first (#88, LOG-07). */
export function ActivityScreen() {
  const [action, setAction] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const filters = { action: action.trim() || undefined, from: from || undefined, to: to || undefined, page };
  const query = useQuery({ queryKey: queryKeys.ownerAudit(filters), queryFn: () => fetchAuditLog(filters), placeholderData: (previous) => previous });

  return (
    <Page>
      <Breadcrumbs items={[{ label: "Reports", href: "/owner/reports" }, { label: "Activity log" }]} />
      <PageHeader title="Activity log" description="Changes made in your library by you, your members and the system." />
      <FilterBar label="Filter activity">
        <FormField label="Action" hint="For example membership.renew" className="sm:w-60">
          <Input value={action} onChange={(event) => { setAction(event.target.value); setPage(1); }} />
        </FormField>
        <FormField label="From" className="sm:w-44">
          <DateField value={from} max={to || undefined} onChange={(event) => { setFrom(event.target.value); setPage(1); }} />
        </FormField>
        <FormField label="To" className="sm:w-44">
          <DateField value={to} min={from || undefined} onChange={(event) => { setTo(event.target.value); setPage(1); }} />
        </FormField>
      </FilterBar>
      {query.isPending ? (
        <LoadingList label="Loading the activity log" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load the activity log." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="No activity found" />
      ) : (
        <>
          <DataTable<AuditEntry>
            caption="Activity"
            rows={query.data.items}
            rowKey={(row) => row.id}
            columns={[
              { key: "when", header: "When", primary: true, cell: (row) => formatDateTime(row.created_at) },
              { key: "who", header: "By", cell: (row) => `${row.actor.name} (${row.actor.role})` },
              { key: "what", header: "Action", cell: (row) => <span title={row.action}>{actionLabel(row.action)}</span> },
              { key: "reason", header: "Reason", hideOnMobile: true, cell: (row) => row.reason || "—" },
            ]}
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
    </Page>
  );
}
