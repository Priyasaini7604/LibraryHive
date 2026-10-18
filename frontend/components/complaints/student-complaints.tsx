"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { Textarea } from "@/components/ui/input";
import { Breadcrumbs, Pagination } from "@/components/ui/navigation";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Fact, LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { CATEGORY_LABEL, ComplaintBadge } from "@/components/ui/status-badges";
import { Alert, Card, CardContent } from "@/components/ui/surface";
import { fetchStudentMemberships } from "@/lib/api/memberships";
import { fetchStudentComplaint, fetchStudentComplaints, raiseComplaint } from "@/lib/api/operations";
import { isApiError, userMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { ComplaintCategory } from "@/lib/types";

const CATEGORY_OPTIONS = (Object.keys(CATEGORY_LABEL) as ComplaintCategory[]).map((value) => ({ value, label: CATEGORY_LABEL[value] }));

function NewComplaintDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const memberships = useQuery({ queryKey: queryKeys.studentMemberships(true), queryFn: () => fetchStudentMemberships(true) });
  const [libraryId, setLibraryId] = useState("");
  const [category, setCategory] = useState<ComplaintCategory | "">("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  // One entry per library, whether the membership is current or past (complaints are open to past members).
  const libraries = [...new Map((memberships.data ?? []).map((m) => [m.library.id, m.library.name])).entries()];
  const chosen = libraryId || (libraries.length === 1 ? (libraries[0]?.[0] ?? "") : "");

  const save = useMutation({
    mutationFn: () => raiseComplaint({ library_id: chosen, category: category as ComplaintCategory, description: description.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["student"] });
      toast.success("Your complaint was sent to the library.");
      onClose();
    },
    onError: (failure) => setError(isApiError(failure, "NO_ACTIVE_MEMBERSHIP") ? "Only members of a library can send it a complaint." : userMessage(failure)),
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title="Raise a complaint" description="The library owner will see this and reply here.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!chosen) return setError("Choose the library.");
            if (!category) return setError("Choose what this is about.");
            if (description.trim().length < 10) return setError("Describe the problem in at least 10 characters.");
            setError(null);
            save.mutate();
          }}
        >
          {memberships.isError ? (
            <Alert tone="danger">We couldn&apos;t load your libraries. Close this window and try again.</Alert>
          ) : libraries.length === 0 && !memberships.isPending ? (
            <Alert tone="info">You can raise a complaint once you have a seat at a library.</Alert>
          ) : (
            <>
              <FormField label="Library" required>
                <Select value={chosen} onValueChange={setLibraryId} placeholder="Choose a library" options={libraries.map(([id, name]) => ({ value: id, label: name }))} />
              </FormField>
              <FormField label="About" required>
                <Select value={category} onValueChange={(value) => setCategory(value as ComplaintCategory)} placeholder="Choose a topic" options={CATEGORY_OPTIONS} />
              </FormField>
              <FormField label="What happened?" required hint="10 to 2000 characters.">
                <Textarea rows={5} maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} />
              </FormField>
            </>
          )}
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending} disabled={libraries.length === 0}>
              Send complaint
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** `/student/complaints`: the student's own complaints and a form to raise one (#71, #72). */
export function StudentComplaintsScreen() {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const query = useQuery({ queryKey: queryKeys.studentComplaints({ page }), queryFn: () => fetchStudentComplaints({ page }), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader
        title="Complaints"
        description="Tell your library about a problem and follow its reply."
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus aria-hidden="true" className="size-4" /> Raise a complaint
          </Button>
        }
      />
      {query.isPending ? (
        <LoadingList label="Loading your complaints" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your complaints." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="No complaints" description="If something at your library needs fixing, raise a complaint and the owner will reply here." />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {query.data.items.map((complaint) => (
              <li key={complaint.id}>
                <Card>
                  <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-4">
                    <div className="flex flex-col gap-1">
                      <p className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
                        {CATEGORY_LABEL[complaint.category]} · {complaint.library.name}
                        <ComplaintBadge status={complaint.status} />
                      </p>
                      <p className="line-clamp-2 text-sm text-slate-700">{complaint.description}</p>
                      <p className="text-xs text-slate-600">Sent {formatDateTime(complaint.created_at)}</p>
                    </div>
                    <Button asChild size="sm" variant="secondary">
                      <Link href={`/student/complaints/${complaint.id}`} aria-label={`Open your ${CATEGORY_LABEL[complaint.category]} complaint`}>
                        Open
                      </Link>
                    </Button>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
      {adding && <NewComplaintDialog onClose={() => setAdding(false)} />}
    </Page>
  );
}

/** `/student/complaints/[id]`: one complaint with the owner's reply (#73). */
export function StudentComplaintDetail({ id }: { id: string }) {
  const query = useQuery({ queryKey: queryKeys.studentComplaint(id), queryFn: () => fetchStudentComplaint(id) });
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
                <Link href="/student/complaints">Complaints</Link>
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
  return (
    <Page>
      <Breadcrumbs items={[{ label: "Complaints", href: "/student/complaints" }, { label: CATEGORY_LABEL[c.category] }]} />
      <PageHeader title={`${CATEGORY_LABEL[c.category]} at ${c.library.name}`} actions={<ComplaintBadge status={c.status} />} />
      <Card>
        <CardContent className="flex flex-col gap-4 pt-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            <Fact label="Sent">{formatDateTime(c.created_at)}</Fact>
            {c.resolved_at && <Fact label="Resolved">{formatDateTime(c.resolved_at)}</Fact>}
          </dl>
          <p className="whitespace-pre-line text-slate-800">{c.description}</p>
        </CardContent>
      </Card>
      {c.owner_response ? (
        <Alert tone="info" title={`Reply from ${c.library.name}`}>
          <span className="whitespace-pre-line">{c.owner_response}</span>
          {c.responded_at && <span className="mt-1 block text-xs">{formatDateTime(c.responded_at)}</span>}
        </Alert>
      ) : (
        <p className="text-sm text-slate-600">The library hasn&apos;t replied yet.</p>
      )}
    </Page>
  );
}
