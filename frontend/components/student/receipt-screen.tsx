"use client";

import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Breadcrumbs } from "@/components/ui/navigation";
import { LoadingList, Page } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { METHOD_LABEL, PaymentBadge } from "@/components/ui/status-badges";
import { Alert } from "@/components/ui/surface";
import { fetchStudentReceipt } from "@/lib/api/payments";
import { isApiError } from "@/lib/errors";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

/** `/student/payments/[id]`: a printable receipt (#45). */
export function ReceiptScreen({ id }: { id: string }) {
  const query = useQuery({ queryKey: queryKeys.studentReceipt(id), queryFn: () => fetchStudentReceipt(id) });

  if (query.isPending) {
    return (
      <Page className="max-w-2xl">
        <LoadingList label="Loading the receipt" rows={2} />
      </Page>
    );
  }
  if (query.isError) {
    return (
      <Page className="max-w-2xl">
        {isApiError(query.error, "NOT_FOUND") ? (
          <EmptyState
            title="We couldn't find this receipt"
            action={
              <Button asChild variant="secondary">
                <Link href="/student/payments">My payments</Link>
              </Button>
            }
          />
        ) : (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load the receipt." />
        )}
      </Page>
    );
  }

  const p = query.data;
  const rows: [string, React.ReactNode][] = [
    ["Receipt number", p.receipt_number],
    ["Date", formatDateTime(p.paid_at ?? p.created_at)],
    ["Library", p.library.name],
    ["For", `${p.purpose === "renewal" ? "Renewal" : "New membership"} · ${p.plan_name}${p.seat_label ? ` · seat ${p.seat_label}` : ""}`],
    ["Period", p.period_start && p.period_end ? `${formatDate(p.period_start)} – ${formatDate(p.period_end)}` : "—"],
    ["Paid by", METHOD_LABEL[p.method]],
    ["Status", <PaymentBadge key="status" status={p.status} />],
  ];

  return (
    <Page className="max-w-2xl">
      <div className="print:hidden">
        <Breadcrumbs items={[{ label: "My payments", href: "/student/payments" }, { label: p.receipt_number }]} />
      </div>
      {p.status === "needs_refund" && (
        <Alert tone="danger" title="A refund is due to you">
          Your payment was received but the seat was no longer available. {p.library.name} will refund you.
        </Alert>
      )}
      <article aria-label="Receipt" className="rounded-xl border border-slate-300 bg-white p-6 print:border-0 print:p-0">
        <header className="mb-4 flex items-start justify-between gap-3 border-b border-slate-200 pb-4">
          <div>
            <p className="text-sm text-slate-600">LibraryHive receipt</p>
            <h1 className="text-xl font-semibold text-slate-900">{p.library.name}</h1>
          </div>
          <p className="text-2xl font-semibold text-slate-900">{formatMoney(p.amount)}</p>
        </header>
        <dl className="grid gap-3 sm:grid-cols-[10rem_1fr]">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-sm text-slate-600">{label}</dt>
              <dd className="text-sm font-medium text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
        <footer className="mt-6 border-t border-slate-200 pt-4 text-sm text-slate-600">
          {[p.library_contact.address, p.library_contact.phone, p.library_contact.email].filter(Boolean).join(" · ")}
        </footer>
      </article>
      <div className="flex gap-2 print:hidden">
        <Button variant="secondary" onClick={() => window.print()}>
          <Printer aria-hidden="true" className="size-4" /> Print receipt
        </Button>
      </div>
    </Page>
  );
}
