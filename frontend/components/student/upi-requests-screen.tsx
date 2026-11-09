"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { UpiRequestSummary } from "@/components/payments/upi-request-summary";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/navigation";
import { ConfirmDialog } from "@/components/ui/overlay";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { cancelUpiRequest, fetchStudentUpiRequests } from "@/lib/api/upi";
import { userMessage } from "@/lib/errors";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 20;

/** `/student/payments/upi`: the student's direct UPI payment requests and what the library decided. */
export function StudentUpiRequestsScreen() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const query = useQuery({
    queryKey: queryKeys.studentUpiRequests({ page }),
    queryFn: () => fetchStudentUpiRequests({ page }),
    placeholderData: (previous) => previous,
  });

  const cancel = useMutation({
    mutationFn: (id: string) => cancelUpiRequest(id),
    onSuccess: async () => {
      setCancelling(null);
      await queryClient.invalidateQueries({ queryKey: ["student"] });
      toast.success("Request cancelled. Nothing was activated.");
    },
    onError: (error) => {
      setCancelling(null);
      toast.error(userMessage(error));
      void queryClient.invalidateQueries({ queryKey: ["student", "upi"] });
    },
  });

  return (
    <Page className="max-w-2xl">
      <PageHeader
        title="My UPI payment requests"
        description="Payments you made directly to a library. A request is only confirmed when the library owner approves it."
      />
      {query.isPending ? (
        <LoadingList label="Loading your payment requests" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your payment requests." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="No UPI payment requests" description="When you pay a library by UPI and send the reference, it will be listed here." />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {query.data.items.map((request) => (
              <li key={request.id}>
                <UpiRequestSummary
                  request={request}
                  actions={
                    request.can_cancel && (
                      <Button variant="secondary" size="sm" className="self-start" onClick={() => setCancelling(request.id)}>
                        Cancel this request
                      </Button>
                    )
                  }
                />
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPageChange={setPage} />
        </>
      )}
      <ConfirmDialog
        open={cancelling !== null}
        onOpenChange={(open) => !open && setCancelling(null)}
        title="Cancel this payment request?"
        description="Only cancel if you did not pay. If you already paid, ask the library to confirm it instead: cancelling does not return your money."
        confirmLabel="Cancel request"
        destructive
        loading={cancel.isPending}
        onConfirm={() => cancelling && cancel.mutate(cancelling)}
      />
    </Page>
  );
}
