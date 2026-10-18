"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { attendanceStatusLabel } from "@/components/attendance/student-attendance-screen";
import { ExportButton } from "@/components/owner/export-button";
import { Button } from "@/components/ui/button";
import { DataTable, FilterBar } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { DateField, Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/navigation";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Alert, Badge } from "@/components/ui/surface";
import { correctAttendance, fetchLiveAttendance, fetchOwnerAttendance, ownerCheckOut } from "@/lib/api/operations";
import { userMessage } from "@/lib/errors";
import { formatDate, formatDateTime, formatDuration } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { OwnerAttendanceRecord } from "@/lib/types";

/** `<input type="datetime-local">` value for an ISO time, shown in the browser's own zone. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function CorrectionDialog({ record, onClose }: { record: OwnerAttendanceRecord; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [checkIn, setCheckIn] = useState(toLocalInput(record.check_in_at));
  const [checkOut, setCheckOut] = useState(toLocalInput(record.check_out_at));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      correctAttendance(record.id, {
        check_in_at: new Date(checkIn).toISOString(),
        ...(checkOut ? { check_out_at: new Date(checkOut).toISOString() } : {}),
        reason: reason.trim(),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["owner", "attendance"] });
      toast.success("Attendance corrected.");
      onClose();
    },
    onError: (failure) => setError(userMessage(failure)),
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={`Correct ${record.student.name}'s times`} description="Use this when a check-in or check-out was missed or wrong. The change and your reason are saved in the activity log.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!checkIn) return setError("Enter the check-in time.");
            if (reason.trim().length < 3) return setError("Enter a reason of at least 3 characters.");
            setError(null);
            save.mutate();
          }}
        >
          <FormField label="Checked in" required>
            <Input type="datetime-local" value={checkIn} onChange={(event) => setCheckIn(event.target.value)} />
          </FormField>
          <FormField label="Checked out" hint={record.check_out_at ? undefined : "Leave empty to keep them checked in."}>
            <Input type="datetime-local" value={checkOut} onChange={(event) => setCheckOut(event.target.value)} />
          </FormField>
          <FormField label="Reason" required>
            <Input value={reason} maxLength={300} onChange={(event) => setReason(event.target.value)} />
          </FormField>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending}>
              Save correction
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function LiveRoster() {
  const queryClient = useQueryClient();
  const live = useQuery({ queryKey: queryKeys.ownerLive, queryFn: fetchLiveAttendance, refetchInterval: 30_000 });
  const checkOut = useMutation({
    mutationFn: (recordId: string) => ownerCheckOut(recordId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["owner"] });
      toast.success("Checked out.");
    },
    onError: (error) => toast.error(userMessage(error)),
  });

  return (
    <section aria-labelledby="live-heading" className="flex flex-col gap-3">
      <h2 id="live-heading" className="text-lg font-semibold text-slate-900">
        In the library now{live.data ? ` (${live.data.length})` : ""}
      </h2>
      {live.isPending ? (
        <LoadingList label="Loading who is in" rows={2} />
      ) : live.isError ? (
        <ErrorState error={live.error} onRetry={() => void live.refetch()} title="We couldn't load who is in." />
      ) : live.data.length === 0 ? (
        <EmptyState title="Nobody is checked in" description="Members who check in appear here." />
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {live.data.map((row) => (
            <li key={row.record_id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex flex-col text-sm">
                <span className="font-medium text-slate-900">{row.student.name}</span>
                <span className="text-slate-600">
                  {row.seat_label ? `Seat ${row.seat_label} · ` : ""}since {formatDateTime(row.check_in_at)}
                </span>
              </div>
              <Button size="sm" variant="secondary" aria-label={`Check out ${row.student.name}`} loading={checkOut.isPending && checkOut.variables === row.record_id} onClick={() => checkOut.mutate(row.record_id)}>
                Check out
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** `/owner/attendance`: the live roster and the library's attendance history with corrections (#66, #67, #69, #70). */
export function OwnerAttendanceScreen() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [correcting, setCorrecting] = useState<OwnerAttendanceRecord | null>(null);
  const filters = { from: from || undefined, to: to || undefined, page };
  const history = useQuery({ queryKey: queryKeys.ownerAttendance(filters), queryFn: () => fetchOwnerAttendance(filters), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader title="Attendance" description="Who is in the library, and who has been." actions={<ExportButton kind="attendance" query={{ from: from || undefined, to: to || undefined }} />} />
      <LiveRoster />

      <section aria-labelledby="history-heading" className="flex flex-col gap-4">
        <h2 id="history-heading" className="text-lg font-semibold text-slate-900">
          History
        </h2>
        <FilterBar label="Filter attendance">
          <FormField label="From" className="sm:w-44">
            <DateField value={from} max={to || undefined} onChange={(event) => { setFrom(event.target.value); setPage(1); }} />
          </FormField>
          <FormField label="To" className="sm:w-44">
            <DateField value={to} min={from || undefined} onChange={(event) => { setTo(event.target.value); setPage(1); }} />
          </FormField>
        </FilterBar>
        {history.isPending ? (
          <LoadingList label="Loading attendance history" />
        ) : history.isError ? (
          <ErrorState error={history.error} onRetry={() => void history.refetch()} title="We couldn't load the history." />
        ) : history.data.items.length === 0 ? (
          <EmptyState title="No attendance recorded" />
        ) : (
          <>
            <DataTable<OwnerAttendanceRecord>
              caption="Attendance history"
              rows={history.data.items}
              rowKey={(row) => row.id}
              columns={[
                { key: "student", header: "Student", primary: true, cell: (row) => row.student.name },
                { key: "date", header: "Date", cell: (row) => formatDate(row.date) },
                { key: "in", header: "In", cell: (row) => formatDateTime(row.check_in_at) },
                { key: "out", header: "Out", cell: (row) => (row.check_out_at ? formatDateTime(row.check_out_at) : "—") },
                { key: "time", header: "Time", hideOnMobile: true, cell: (row) => formatDuration(row.duration_minutes) },
                { key: "status", header: "Status", hideOnMobile: true, cell: (row) => <Badge tone={row.status === "open" ? "info" : "neutral"}>{attendanceStatusLabel(row)}</Badge> },
              ]}
              rowActions={(row) => (
                <Button size="sm" variant="secondary" aria-label={`Correct ${row.student.name}'s times`} onClick={() => setCorrecting(row)}>
                  Correct
                </Button>
              )}
            />
            <Pagination page={history.data.page} pageSize={history.data.page_size} total={history.data.total} onPageChange={setPage} />
          </>
        )}
      </section>
      {correcting && <CorrectionDialog record={correcting} onClose={() => setCorrecting(null)} />}
    </Page>
  );
}
