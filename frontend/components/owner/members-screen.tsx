"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ExportButton } from "@/components/owner/export-button";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { DataTable, FilterBar } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/navigation";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { MembershipBadge } from "@/components/ui/status-badges";
import { Badge } from "@/components/ui/surface";
import { fetchMembers, type MemberFilters } from "@/lib/api/memberships";
import { formatDate, formatPhone } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { OwnerMember } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "current", label: "Everyone current" },
  { value: "active", label: "Active" },
  { value: "due", label: "Due soon" },
  { value: "overdue", label: "Overdue" },
  { value: "archived", label: "Ended" },
];
const SOURCE_OPTIONS = [
  { value: "any", label: "Any source" },
  { value: "online", label: "Booked online" },
  { value: "offline", label: "Added by you" },
];

/** `/owner/members`: the unified member directory (#50). */
export function MembersScreen() {
  const [status, setStatus] = useState("current");
  const [source, setSource] = useState("any");
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(text.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [text]);

  const filters: MemberFilters = {
    status: status as MemberFilters["status"],
    source: source === "any" ? undefined : (source as MemberFilters["source"]),
    search: search || undefined,
    page,
  };
  const query = useQuery({ queryKey: queryKeys.ownerMembers(filters), queryFn: () => fetchMembers(filters), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader
        title="Members"
        description="Everyone with a seat in your library, whether they booked online or you added them."
        actions={
          <>
            <ExportButton kind="members" query={{ status: status === "current" ? undefined : status }} />
            <Button asChild>
              <Link href="/owner/members/new">
                <Plus aria-hidden="true" className="size-4" /> Admit a student
              </Link>
            </Button>
          </>
        }
      />
      <FilterBar label="Filter members">
        <FormField label="Search" className="sm:w-64">
          <Input type="search" value={text} placeholder="Name, phone or seat" onChange={(event) => setText(event.target.value)} />
        </FormField>
        <FormField label="Status" className="sm:w-48">
          <Select value={status} onValueChange={(value) => { setStatus(value); setPage(1); }} options={STATUS_OPTIONS} />
        </FormField>
        <FormField label="Source" className="sm:w-48">
          <Select value={source} onValueChange={(value) => { setSource(value); setPage(1); }} options={SOURCE_OPTIONS} />
        </FormField>
      </FilterBar>

      {query.isPending ? (
        <LoadingList label="Loading members" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your members." />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          title={search || status !== "current" || source !== "any" ? "No members match these filters" : "No members yet"}
          description="Admit a student who walked in, or wait for online bookings."
          action={
            <Button asChild>
              <Link href="/owner/members/new">Admit a student</Link>
            </Button>
          }
        />
      ) : (
        <>
          <DataTable<OwnerMember>
            caption="Members"
            rows={query.data.items}
            rowKey={(row) => row.membership_id}
            columns={[
              {
                key: "name",
                header: "Name",
                primary: true,
                cell: (row) => (
                  <span className="flex flex-wrap items-center gap-2">
                    <Link href={`/owner/members/${row.membership_id}`} className="font-medium text-blue-700 hover:underline">
                      {row.student.name}
                    </Link>
                    {row.student.is_offline && <Badge>Added by you</Badge>}
                  </span>
                ),
              },
              { key: "phone", header: "Phone", cell: (row) => formatPhone(row.student.phone) },
              { key: "seat", header: "Seat", cell: (row) => row.seat.label },
              { key: "plan", header: "Plan", hideOnMobile: true, cell: (row) => row.plan.name },
              { key: "status", header: "Status", cell: (row) => <MembershipBadge status={row.status} /> },
              { key: "due", header: "Valid until", cell: (row) => formatDate(row.next_due_date) },
            ]}
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
    </Page>
  );
}
