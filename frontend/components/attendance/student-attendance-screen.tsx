"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { CheckInCard } from "@/components/attendance/check-in-card";
import { StatCard } from "@/components/charts/stat-card";
import { DataTable } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/navigation";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Badge } from "@/components/ui/surface";
import { fetchAttendanceHistory } from "@/lib/api/operations";
import { businessDate, formatDate, formatDateTime, formatDuration } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { AttendanceRecord } from "@/lib/types";

export function attendanceStatusLabel(record: Pick<AttendanceRecord, "status">): string {
  return record.status === "open" ? "In the library" : record.status === "auto_closed" ? "Closed automatically" : "Checked out";
}

/** `/student/attendance`: check in or out, and the student's own history by month (#62-#65, ATT-04). */
export function StudentAttendanceScreen() {
  const [month, setMonth] = useState(() => businessDate().slice(0, 7));
  const [page, setPage] = useState(1);
  const filters = { month: month || undefined, page };
  const query = useQuery({ queryKey: queryKeys.attendanceHistory(filters), queryFn: () => fetchAttendanceHistory(filters), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader title="Attendance" description="Check in when you arrive and out when you leave." />
      <CheckInCard />

      <section aria-labelledby="history-heading" className="flex flex-col gap-4">
        <h2 id="history-heading" className="text-lg font-semibold text-slate-900">
          My history
        </h2>
        <FormField label="Month" className="sm:w-48">
          <Input type="month" value={month} max={businessDate().slice(0, 7)} onChange={(event) => { setMonth(event.target.value); setPage(1); }} />
        </FormField>

        {query.isPending ? (
          <LoadingList label="Loading your attendance" />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your attendance." />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <StatCard label="Days present" value={query.data.summary.days_present} />
              <StatCard label="Time in the library" value={formatDuration(query.data.summary.total_minutes)} />
            </div>
            {query.data.items.length === 0 ? (
              <EmptyState title="No attendance this month" description="Your check-ins will be listed here." />
            ) : (
              <>
                <DataTable<AttendanceRecord>
                  caption="Your attendance"
                  rows={query.data.items}
                  rowKey={(row) => row.id}
                  columns={[
                    { key: "date", header: "Date", primary: true, cell: (row) => formatDate(row.date) },
                    { key: "library", header: "Library", cell: (row) => row.library.name },
                    { key: "in", header: "In", cell: (row) => formatDateTime(row.check_in_at) },
                    { key: "out", header: "Out", cell: (row) => (row.check_out_at ? formatDateTime(row.check_out_at) : "—") },
                    { key: "time", header: "Time", cell: (row) => formatDuration(row.duration_minutes) },
                    {
                      key: "status",
                      header: "Status",
                      hideOnMobile: true,
                      cell: (row) => <Badge tone={row.status === "open" ? "info" : "neutral"}>{attendanceStatusLabel(row)}</Badge>,
                    },
                  ]}
                />
                <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
              </>
            )}
          </>
        )}
      </section>
    </Page>
  );
}
