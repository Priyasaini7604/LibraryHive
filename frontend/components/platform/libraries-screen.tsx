"use client";

import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";

import { RangeFilter, useDateRange } from "@/components/platform/range-filter";
import { FormField } from "@/components/ui/form-field";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/navigation";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Alert, Badge } from "@/components/ui/surface";
import { fetchPlatformLibraries } from "@/lib/api/platform";
import type { LibraryOrdering, PlatformLibraryRow } from "@/lib/platform-types";
import { queryKeys } from "@/lib/query-keys";

const ORDERINGS: { value: LibraryOrdering; label: string }[] = [
  { value: "bookings", label: "Bookings in range" },
  { value: "total_bookings", label: "All-time bookings" },
  { value: "members", label: "Registered members" },
  { value: "active_members", label: "Active members" },
  { value: "online_students", label: "Students via LibraryHive" },
  { value: "check_ins", label: "Check-ins in range" },
  { value: "name", label: "Name" },
];

/** `/platform/libraries`: one row per library, aggregates only, paginated on the server. */
export function PlatformLibrariesScreen() {
  const [state, setState] = useDateRange();
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState<LibraryOrdering>("bookings");
  const [page, setPage] = useState(1);
  const deferredSearch = useDeferredValue(search.trim());
  const { range } = state;
  const valid = range.to >= range.from;
  const filters = { ...range, page, search: deferredSearch, ordering, descending: ordering !== "name" };
  const query = useQuery({
    queryKey: queryKeys.platformLibraries(filters),
    queryFn: () => fetchPlatformLibraries(filters),
    enabled: valid,
  });

  return (
    <Page className="max-w-7xl">
      <PageHeader
        title="Library performance"
        description="Which libraries are getting the most use through LibraryHive. Counts only; no student details."
        actions={
          <RangeFilter
            value={state}
            onChange={(next) => {
              setState(next);
              setPage(1);
            }}
          />
        }
      />
      <Alert tone="info" title="Subscription plan and status are not tracked yet">
        LibraryHive has no library subscription model, so those columns show a dash until one exists.
      </Alert>
      <div className="flex flex-wrap items-end gap-3">
        <FormField label="Search" className="sm:w-64">
          <Input
            type="search"
            value={search}
            placeholder="Library or city"
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </FormField>
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-900 sm:w-64">
          Sort by
          <select
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm"
            value={ordering}
            onChange={(event) => {
              setOrdering(event.target.value as LibraryOrdering);
              setPage(1);
            }}
          >
            {ORDERINGS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!valid ? null : query.isPending ? (
        <LoadingList label="Loading libraries" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We could not load libraries." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title={deferredSearch ? "No libraries match this search" : "No libraries yet"} />
      ) : (
        <>
          <DataTable<PlatformLibraryRow>
            caption="Library performance"
            rows={query.data.items}
            rowKey={(row) => row.id}
            columns={[
              {
                key: "name",
                header: "Library",
                primary: true,
                cell: (row) => (
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{row.name}</span>
                    <span className="text-slate-600">{row.city}</span>
                    {!row.is_published && <Badge>Unpublished</Badge>}
                  </span>
                ),
              },
              { key: "range", header: "Bookings in range", cell: (row) => row.bookings_in_range, className: "tabular-nums" },
              { key: "students", header: "Unique students in range", cell: (row) => row.unique_students_in_range, className: "tabular-nums" },
              { key: "total", header: "All-time bookings", hideOnMobile: true, cell: (row) => row.total_bookings, className: "tabular-nums" },
              { key: "members", header: "Registered members", cell: (row) => row.registered_members, className: "tabular-nums" },
              { key: "active", header: "Active members", hideOnMobile: true, cell: (row) => row.active_members, className: "tabular-nums" },
              { key: "online", header: "Students via LibraryHive", hideOnMobile: true, cell: (row) => row.online_students, className: "tabular-nums" },
              { key: "checkins", header: "Check-ins in range", hideOnMobile: true, cell: (row) => row.check_ins_in_range, className: "tabular-nums" },
              { key: "plan", header: "Subscription", hideOnMobile: true, cell: (row) => row.subscription_plan ?? "—" },
            ]}
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
    </Page>
  );
}
