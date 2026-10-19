"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Pagination } from "@/components/ui/navigation";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { METHOD_LABEL, PaymentBadge } from "@/components/ui/status-badges";
import { fetchStudentPayments } from "@/lib/api/payments";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { StudentPayment } from "@/lib/types";

/** `/student/payments`: every payment attempt, newest first, with receipts for paid ones (#44). */
export function PaymentsScreen() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: queryKeys.studentPayments({ page }), queryFn: () => fetchStudentPayments({ page }), placeholderData: (previous) => previous });

  return (
    <Page>
      <PageHeader title="My payments" description="Receipts for everything you've paid, and payments still being confirmed." />
      {query.isPending ? (
        <LoadingList label="Loading your payments" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your payments." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="No payments yet" description="Payments you make to a library will be listed here." />
      ) : (
        <>
          <DataTable<StudentPayment>
            caption="Your payments"
            rows={query.data.items}
            rowKey={(row) => row.id}
            columns={[
              { key: "date", header: "Date", primary: true, cell: (row) => formatDateTime(row.paid_at ?? row.created_at) },
              { key: "library", header: "Library", cell: (row) => row.library.name },
              { key: "purpose", header: "For", cell: (row) => (row.purpose === "renewal" ? "Renewal" : "New membership") },
              { key: "amount", header: "Amount", cell: (row) => formatMoney(row.amount) },
              { key: "method", header: "Paid by", hideOnMobile: true, cell: (row) => METHOD_LABEL[row.method] },
              { key: "status", header: "Status", cell: (row) => <PaymentBadge status={row.status} /> },
              {
                key: "period",
                header: "Period",
                hideOnMobile: true,
                cell: (row) => (row.period_start && row.period_end ? `${formatDate(row.period_start)} – ${formatDate(row.period_end)}` : "—"),
              },
            ]}
            rowActions={(row) =>
              row.status === "success" || row.status === "needs_refund" ? (
                <Button asChild size="sm" variant="secondary">
                  <Link href={`/student/payments/${row.id}`} aria-label={`Receipt ${row.receipt_number}`}>
                    Receipt
                  </Link>
                </Button>
              ) : null
            }
          />
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
    </Page>
  );
}
