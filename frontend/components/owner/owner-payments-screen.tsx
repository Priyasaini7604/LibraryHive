"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ExportButton } from "@/components/owner/export-button";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { DataTable, FilterBar } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { DateField, Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/navigation";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Fact, LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { METHOD_LABEL, PaymentBadge } from "@/components/ui/status-badges";
import { fetchOwnerPayment, fetchOwnerPayments, type OwnerPaymentFilters } from "@/lib/api/payments";
import { formatDate, formatDateTime, formatMoney, formatPhone } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { OwnerPayment } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "any", label: "Any status" },
  { value: "success", label: "Paid" },
  { value: "pending", label: "Pending" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "needs_refund", label: "Refund due" },
];
const METHOD_OPTIONS = [
  { value: "any", label: "Any method" },
  { value: "gateway", label: "Online" },
  { value: "cash", label: "Cash" },
  { value: "upi_direct", label: "UPI (direct)" },
  { value: "bank_transfer", label: "Bank transfer" },
];

function PaymentDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const query = useQuery({ queryKey: queryKeys.ownerPayment(id), queryFn: () => fetchOwnerPayment(id) });
  const p = query.data;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={p ? `Receipt ${p.receipt_number}` : "Payment"} description={p ? `${p.student.name} · ${formatMoney(p.amount)}` : undefined}>
        {query.isPending ? (
          <LoadingList label="Loading the payment" rows={2} />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load this payment." />
        ) : p ? (
          <dl className="grid gap-3 sm:grid-cols-2">
            <Fact label="Status">
              <PaymentBadge status={p.status} />
            </Fact>
            <Fact label="Date">{formatDateTime(p.paid_at ?? p.created_at)}</Fact>
            <Fact label="Student">
              {p.student.name} · {formatPhone(p.student.phone)}
            </Fact>
            <Fact label="For">
              {p.purpose === "renewal" ? "Renewal" : "New membership"} · {p.plan_name}
              {p.seat_label ? ` · seat ${p.seat_label}` : ""}
            </Fact>
            <Fact label="Period">{p.period_start && p.period_end ? `${formatDate(p.period_start)} – ${formatDate(p.period_end)}` : "—"}</Fact>
            <Fact label="Paid by">
              {METHOD_LABEL[p.method]}
              {p.recorded_by ? ` · recorded by ${p.recorded_by.name}` : ""}
            </Fact>
            {p.notes && <Fact label="Note">{p.notes}</Fact>}
            {p.failure_reason && <Fact label="Why it needs attention">{p.failure_reason}</Fact>}
          </dl>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

/** `/owner/payments`: the library's payment ledger with filters and export (#46, #47, #87). */
export function OwnerPaymentsScreen() {
  const [status, setStatus] = useState("any");
  const [method, setMethod] = useState("any");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(text.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [text]);

  const filters: OwnerPaymentFilters = {
    status: status === "any" ? undefined : (status as OwnerPaymentFilters["status"]),
    method: method === "any" ? undefined : (method as OwnerPaymentFilters["method"]),
    date_from: from || undefined,
    date_to: to || undefined,
    search: search || undefined,
    page,
  };
  const query = useQuery({ queryKey: queryKeys.ownerPayments(filters), queryFn: () => fetchOwnerPayments(filters), placeholderData: (previous) => previous });
  const reset = (setter: (value: string) => void) => (value: string) => {
    setter(value);
    setPage(1);
  };

  return (
    <Page>
      <PageHeader
        title="Payments"
        description="Every online and offline payment for your library."
        actions={<ExportButton kind="payments" query={{ from: from || undefined, to: to || undefined }} />}
      />
      <FilterBar label="Filter payments">
        <FormField label="Search" className="sm:w-56">
          <Input type="search" value={text} placeholder="Student name or phone" onChange={(event) => setText(event.target.value)} />
        </FormField>
        <FormField label="Status" className="sm:w-44">
          <Select value={status} onValueChange={reset(setStatus)} options={STATUS_OPTIONS} />
        </FormField>
        <FormField label="Method" className="sm:w-44">
          <Select value={method} onValueChange={reset(setMethod)} options={METHOD_OPTIONS} />
        </FormField>
        <FormField label="From" className="sm:w-40">
          <DateField value={from} max={to || undefined} onChange={(event) => reset(setFrom)(event.target.value)} />
        </FormField>
        <FormField label="To" className="sm:w-40">
          <DateField value={to} min={from || undefined} onChange={(event) => reset(setTo)(event.target.value)} />
        </FormField>
      </FilterBar>

      {query.isPending ? (
        <LoadingList label="Loading payments" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your payments." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="No payments match" description="Payments appear here as students pay online or you record them." />
      ) : (
        <>
          <DataTable<OwnerPayment>
            caption="Payments"
            rows={query.data.items}
            rowKey={(row) => row.id}
            columns={[
              { key: "date", header: "Date", primary: true, cell: (row) => formatDateTime(row.paid_at ?? row.created_at) },
              { key: "student", header: "Student", cell: (row) => row.student.name },
              { key: "amount", header: "Amount", cell: (row) => formatMoney(row.amount) },
              { key: "method", header: "Paid by", cell: (row) => METHOD_LABEL[row.method] },
              { key: "status", header: "Status", cell: (row) => <PaymentBadge status={row.status} /> },
              { key: "receipt", header: "Receipt", hideOnMobile: true, cell: (row) => row.receipt_number },
            ]}
            rowActions={(row) => (
              <Button size="sm" variant="secondary" aria-label={`Details of ${row.receipt_number}`} onClick={() => setOpenId(row.id)}>
                Details
              </Button>
            )}
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
      {openId && <PaymentDialog id={openId} onClose={() => setOpenId(null)} />}
    </Page>
  );
}
