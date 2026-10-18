"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { DataTable, FilterBar } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/navigation";
import { ConfirmDialog, Dialog, DialogContent } from "@/components/ui/overlay";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SLOT_LABEL, VisitBadge } from "@/components/ui/status-badges";
import { Alert, Card, CardContent } from "@/components/ui/surface";
import { cancelVisit, decideVisit, fetchOwnerVisits, fetchStudentVisits } from "@/lib/api/operations";
import { userMessage } from "@/lib/errors";
import { formatDate, formatDateTime, formatPhone } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { OwnerVisit, Visit, VisitStatus } from "@/lib/types";

/** `/student/visits`: the student's visit requests, with withdrawal of a pending one (#78, #79). */
export function StudentVisitsScreen() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [cancelling, setCancelling] = useState<Visit | null>(null);
  const query = useQuery({ queryKey: queryKeys.studentVisits({ page }), queryFn: () => fetchStudentVisits({ page }), placeholderData: (previous) => previous });

  const cancel = useMutation({
    mutationFn: (visit: Visit) => cancelVisit(visit.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["student"] });
      toast.success("Visit request cancelled.");
      setCancelling(null);
    },
    onError: (error) => {
      toast.error(userMessage(error));
      setCancelling(null);
      void queryClient.invalidateQueries({ queryKey: ["student", "visits"] });
    },
  });

  return (
    <Page>
      <PageHeader title="Visit requests" description="Libraries you've asked to look around. Request a visit from a library's page." />
      {query.isPending ? (
        <LoadingList label="Loading your visit requests" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your visit requests." />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          title="No visit requests"
          description="Want to see a library before you book? Open it and choose Request a visit."
          action={
            <Button asChild>
              <Link href="/discover">Find a library</Link>
            </Button>
          }
        />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {query.data.items.map((visit) => (
              <li key={visit.id}>
                <Card>
                  <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-4">
                    <div className="flex flex-col gap-1">
                      <p className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
                        {visit.library.name}
                        <VisitBadge status={visit.status} />
                      </p>
                      <p className="text-sm text-slate-700">
                        {formatDate(visit.preferred_date)} · {SLOT_LABEL[visit.preferred_slot]}
                      </p>
                      {visit.owner_note && <p className="text-sm text-slate-700">Library says: {visit.owner_note}</p>}
                    </div>
                    {visit.status === "pending" && (
                      <Button size="sm" variant="secondary" aria-label={`Cancel your visit request to ${visit.library.name}`} onClick={() => setCancelling(visit)}>
                        Cancel request
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
      <ConfirmDialog
        open={cancelling !== null}
        onOpenChange={(open) => !open && setCancelling(null)}
        title="Cancel this visit request?"
        description="The library won't see it any more. You can send a new request later."
        confirmLabel="Cancel request"
        destructive
        loading={cancel.isPending}
        onConfirm={() => cancelling && cancel.mutate(cancelling)}
      />
    </Page>
  );
}

const STATUS_OPTIONS = [
  { value: "any", label: "Any status" },
  { value: "pending", label: "Waiting for you" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Declined" },
  { value: "cancelled", label: "Cancelled" },
];

function DecisionDialog({ visit, decision, onClose }: { visit: OwnerVisit; decision: "accept" | "reject"; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => decideVisit(visit.id, { decision, ...(note.trim() ? { owner_note: note.trim() } : {}) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["owner"] });
      toast.success(decision === "accept" ? "Visit accepted. The student was told." : "Visit declined. The student was told.");
      onClose();
    },
    onError: (failure) => setError(userMessage(failure)),
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={`${decision === "accept" ? "Accept" : "Decline"} ${visit.student.name}'s visit`}
        description={`${formatDate(visit.preferred_date)} · ${SLOT_LABEL[visit.preferred_slot]}`}
      >
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          <FormField label="Note to the student" hint="Optional, for example the time you'll be there.">
            <Input value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} />
          </FormField>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" variant={decision === "accept" ? "primary" : "danger"} loading={save.isPending}>
              {decision === "accept" ? "Accept visit" : "Decline visit"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** `/owner/visits`: the visit inbox with accept and decline (#80, #81). */
export function OwnerVisitsScreen() {
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [deciding, setDeciding] = useState<{ visit: OwnerVisit; decision: "accept" | "reject" } | null>(null);
  const filters = { status: status === "any" ? undefined : (status as VisitStatus), page };
  const query = useQuery({ queryKey: queryKeys.ownerVisits(filters), queryFn: () => fetchOwnerVisits(filters), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader title="Visit requests" description="Students who want to look around before they book." />
      <FilterBar label="Filter visit requests">
        <FormField label="Status" className="sm:w-52">
          <Select value={status} onValueChange={(value) => { setStatus(value); setPage(1); }} options={STATUS_OPTIONS} />
        </FormField>
      </FilterBar>
      {query.isPending ? (
        <LoadingList label="Loading visit requests" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load visit requests." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title={status === "pending" ? "Nothing waiting" : "No visit requests"} description="New requests appear here and as a notification." />
      ) : (
        <>
          <DataTable<OwnerVisit>
            caption="Visit requests"
            rows={query.data.items}
            rowKey={(row) => row.id}
            columns={[
              { key: "student", header: "Student", primary: true, cell: (row) => `${row.student.name} · ${formatPhone(row.student.phone)}` },
              { key: "when", header: "When", cell: (row) => `${formatDate(row.preferred_date)} · ${SLOT_LABEL[row.preferred_slot]}` },
              { key: "note", header: "Note", hideOnMobile: true, cell: (row) => row.student_note || "—" },
              { key: "status", header: "Status", cell: (row) => <VisitBadge status={row.status} /> },
              { key: "sent", header: "Sent", hideOnMobile: true, cell: (row) => formatDateTime(row.created_at) },
            ]}
            rowActions={(row) =>
              row.status === "pending" ? (
                <span className="flex gap-2">
                  <Button size="sm" aria-label={`Accept ${row.student.name}'s visit`} onClick={() => setDeciding({ visit: row, decision: "accept" })}>
                    Accept
                  </Button>
                  <Button size="sm" variant="secondary" aria-label={`Decline ${row.student.name}'s visit`} onClick={() => setDeciding({ visit: row, decision: "reject" })}>
                    Decline
                  </Button>
                </span>
              ) : null
            }
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
      {deciding && <DecisionDialog visit={deciding.visit} decision={deciding.decision} onClose={() => setDeciding(null)} />}
    </Page>
  );
}
