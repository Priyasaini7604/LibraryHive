"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { DataTable, FilterBar } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { Textarea } from "@/components/ui/input";
import { Breadcrumbs, Pagination } from "@/components/ui/navigation";
import { Fact, LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { CATEGORY_LABEL, ComplaintBadge } from "@/components/ui/status-badges";
import { Alert, Card, CardContent } from "@/components/ui/surface";
import { fetchOwnerComplaint, fetchOwnerComplaints, respondToComplaint } from "@/lib/api/operations";
import { isApiError, userMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { ComplaintCategory, ComplaintStatus, OwnerComplaint } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "any", label: "Any status" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
];
const CATEGORY_OPTIONS = [
  { value: "any", label: "Any topic" },
  ...(Object.keys(CATEGORY_LABEL) as ComplaintCategory[]).map((value) => ({ value, label: CATEGORY_LABEL[value] })),
];

/** `/owner/complaints`: the inbox (#74). */
export function OwnerComplaintsScreen() {
  const [status, setStatus] = useState("any");
  const [category, setCategory] = useState("any");
  const [page, setPage] = useState(1);
  const filters = {
    status: status === "any" ? undefined : (status as ComplaintStatus),
    category: category === "any" ? undefined : (category as ComplaintCategory),
    page,
  };
  const query = useQuery({ queryKey: queryKeys.ownerComplaints(filters), queryFn: () => fetchOwnerComplaints(filters), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader title="Complaints" description="What your members have raised, newest first." />
      <FilterBar label="Filter complaints">
        <FormField label="Status" className="sm:w-48">
          <Select value={status} onValueChange={(value) => { setStatus(value); setPage(1); }} options={STATUS_OPTIONS} />
        </FormField>
        <FormField label="Topic" className="sm:w-56">
          <Select value={category} onValueChange={(value) => { setCategory(value); setPage(1); }} options={CATEGORY_OPTIONS} />
        </FormField>
      </FilterBar>
      {query.isPending ? (
        <LoadingList label="Loading complaints" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your complaints." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="No complaints" description="Complaints from your members will appear here." />
      ) : (
        <>
          <DataTable<OwnerComplaint>
            caption="Complaints"
            rows={query.data.items}
            rowKey={(row) => row.id}
            columns={[
              {
                key: "topic",
                header: "Topic",
                primary: true,
                cell: (row) => (
                  <Link href={`/owner/complaints/${row.id}`} className="font-medium text-blue-700 hover:underline">
                    {CATEGORY_LABEL[row.category]}
                  </Link>
                ),
              },
              { key: "student", header: "From", cell: (row) => `${row.student.name}${row.seat_label ? ` (seat ${row.seat_label})` : ""}` },
              { key: "status", header: "Status", cell: (row) => <ComplaintBadge status={row.status} /> },
              { key: "date", header: "Sent", hideOnMobile: true, cell: (row) => formatDateTime(row.created_at) },
            ]}
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
    </Page>
  );
}

/** `/owner/complaints/[id]`: read a complaint and answer or resolve it (#75, #76). */
export function OwnerComplaintDetail({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.ownerComplaint(id), queryFn: () => fetchOwnerComplaint(id) });
  const [response, setResponse] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (input: { status?: "in_progress" | "resolved"; owner_response?: string }) => respondToComplaint(id, input),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["owner"] });
      queryClient.setQueryData(queryKeys.ownerComplaint(id), updated);
      setResponse(null);
      setError(null);
      toast.success(updated.status === "resolved" ? "Complaint resolved." : "Saved.");
    },
    onError: (failure) => setError(isApiError(failure, "INVALID_TRANSITION") ? "This complaint can't be changed any more." : userMessage(failure)),
  });

  if (query.isPending) {
    return (
      <Page>
        <LoadingList label="Loading the complaint" rows={2} />
      </Page>
    );
  }
  if (query.isError) {
    return (
      <Page>
        {isApiError(query.error, "NOT_FOUND") ? (
          <EmptyState
            title="We couldn't find this complaint"
            action={
              <Button asChild variant="secondary">
                <Link href="/owner/complaints">Complaints</Link>
              </Button>
            }
          />
        ) : (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load this complaint." />
        )}
      </Page>
    );
  }

  const c = query.data;
  const text = response ?? c.owner_response;
  const resolved = c.status === "resolved";

  return (
    <Page>
      <Breadcrumbs items={[{ label: "Complaints", href: "/owner/complaints" }, { label: CATEGORY_LABEL[c.category] }]} />
      <PageHeader title={CATEGORY_LABEL[c.category]} description={`From ${c.student.name}${c.seat_label ? `, seat ${c.seat_label}` : ""}`} actions={<ComplaintBadge status={c.status} />} />
      <Card>
        <CardContent className="flex flex-col gap-4 pt-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            <Fact label="Sent">{formatDateTime(c.created_at)}</Fact>
            {c.resolved_at && <Fact label="Resolved">{formatDateTime(c.resolved_at)}</Fact>}
          </dl>
          <p className="whitespace-pre-line text-slate-800">{c.description}</p>
        </CardContent>
      </Card>

      {resolved ? (
        <Alert tone="success" title="Resolved">
          <span className="whitespace-pre-line">{c.owner_response}</span>
        </Alert>
      ) : (
        <form
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(event) => event.preventDefault()}
          aria-label="Reply to this complaint"
        >
          <FormField label="Your reply" hint="The student sees this. A reply is required to resolve the complaint.">
            <Textarea rows={5} maxLength={2000} value={text} onChange={(event) => setResponse(event.target.value)} />
          </FormField>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              loading={save.isPending && save.variables?.status === undefined}
              disabled={!text.trim() || text.trim() === c.owner_response}
              onClick={() => save.mutate({ owner_response: text.trim() })}
            >
              Send reply
            </Button>
            {c.status === "open" && (
              <Button variant="secondary" loading={save.isPending && save.variables?.status === "in_progress"} onClick={() => save.mutate({ status: "in_progress", ...(text.trim() ? { owner_response: text.trim() } : {}) })}>
                Mark in progress
              </Button>
            )}
            <Button
              loading={save.isPending && save.variables?.status === "resolved"}
              onClick={() => {
                if (!text.trim()) return setError("Write a reply before resolving.");
                save.mutate({ status: "resolved", owner_response: text.trim() });
              }}
            >
              Resolve
            </Button>
          </div>
        </form>
      )}
    </Page>
  );
}
