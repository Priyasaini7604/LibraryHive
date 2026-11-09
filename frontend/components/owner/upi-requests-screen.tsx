"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { UpiStatusBadge, waitingText } from "@/components/payments/upi-request-summary";
import { Button } from "@/components/ui/button";
import { Checkbox, Select } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { Pagination } from "@/components/ui/navigation";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { ReasonDialog } from "@/components/ui/reason-dialog";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Card, CardContent } from "@/components/ui/surface";
import { fetchOwnerSeats } from "@/lib/api/seats";
import { approveUpiRequest, fetchOwnerUpiRequests, fetchOwnerUpiScreenshot, rejectUpiRequest } from "@/lib/api/upi";
import { isApiError, userMessage } from "@/lib/errors";
import { formatDateTime, formatMoney, formatPhone } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { OwnerUpiRequest, UpiRequestStatus } from "@/lib/types";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = [
  { value: "pending", label: "Waiting for you" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "cancelled", label: "Cancelled by student" },
  { value: "any", label: "All" },
];

function ScreenshotDialog({ request, onClose }: { request: OwnerUpiRequest; onClose: () => void }) {
  const query = useQuery({
    queryKey: ["owner", "upi", "screenshot", request.id],
    queryFn: () => fetchOwnerUpiScreenshot(request.id),
    staleTime: 0,
    gcTime: 0,
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title="Payment screenshot" description="Sent by the student. It is not proof of payment: check your own UPI or bank history.">
        {query.isPending ? (
          <Skeleton className="h-72 w-full" />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load the screenshot." />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- a short-lived signed link; next/image would cache it
          <img src={query.data.url} alt="Payment screenshot sent by the student" className="max-h-[70vh] w-full rounded-lg border border-slate-200 object-contain" />
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Approve only after the owner confirms they saw the money. If the seat is gone, offer another seat or a rejection. */
function ApproveDialog({ request, onClose }: { request: OwnerUpiRequest; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [checked, setChecked] = useState(false);
  const [seatTaken, setSeatTaken] = useState<string | null>(null);
  const [seatId, setSeatId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const seats = useQuery({ queryKey: queryKeys.ownerSeats, queryFn: () => fetchOwnerSeats(), enabled: seatTaken !== null });
  const freeSeats = (seats.data?.seats ?? []).filter((seat) => seat.is_active && !seat.is_disabled && seat.status === "empty");

  const approve = useMutation({
    mutationFn: (chosenSeat?: string) => approveUpiRequest(request.id, chosenSeat),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["owner"] });
      toast.success("Payment approved. The membership is active.");
      onClose();
    },
    onError: (failure) => {
      if (isApiError(failure, "SEAT_UNAVAILABLE") && request.purpose === "new_membership") setSeatTaken(failure.message);
      else setError(userMessage(failure));
      if (isApiError(failure, "ALREADY_DECIDED")) void queryClient.invalidateQueries({ queryKey: ["owner", "upi"] });
    },
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={`Approve ${formatMoney(request.amount)} from ${request.student.name}?`}
        description="Approving activates the membership and records a payment receipt. It cannot be undone."
        footer={
          <>
            <Button variant="secondary" onClick={onClose} disabled={approve.isPending}>
              Cancel
            </Button>
            {seatTaken ? (
              <Button loading={approve.isPending} disabled={!seatId} onClick={() => approve.mutate(seatId)}>
                Approve on this seat
              </Button>
            ) : (
              <Button loading={approve.isPending} disabled={!checked} onClick={() => approve.mutate(undefined)}>
                Approve payment
              </Button>
            )}
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <dl className="grid gap-1 text-sm">
            <div>
              <dt className="inline text-slate-600">UTR: </dt>
              <dd className="inline font-mono text-slate-900">{request.utr}</dd>
            </div>
            <div>
              <dt className="inline text-slate-600">Amount to look for: </dt>
              <dd className="inline font-semibold text-slate-900">{formatMoney(request.amount)}</dd>
            </div>
          </dl>
          {seatTaken ? (
            <>
              <Alert tone="warning" title="That seat is no longer free">
                {seatTaken}
              </Alert>
              <FormField label="Another free seat">
                <Select
                  value={seatId}
                  onValueChange={setSeatId}
                  placeholder={seats.isPending ? "Loading seats" : freeSeats.length ? "Choose a seat" : "No free seats"}
                  options={freeSeats.map((seat) => ({ value: seat.id, label: `Seat ${seat.label}` }))}
                />
              </FormField>
              <p className="text-sm text-slate-700">Or close this and reject the request, then refund the student yourself.</p>
            </>
          ) : (
            <Checkbox label="I have seen this exact amount credited in my UPI or bank history" checked={checked} onCheckedChange={setChecked} />
          )}
          {error && <Alert tone="danger">{error}</Alert>}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RequestCard({ request, onApprove, onReject, onScreenshot }: { request: OwnerUpiRequest; onApprove: () => void; onReject: () => void; onScreenshot: () => void }) {
  return (
    <Card aria-label={`Payment request from ${request.student.name}`}>
      <CardContent className="flex flex-col gap-2 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-semibold text-slate-900">
            {request.student.name} · {formatPhone(request.student.phone)}
          </p>
          <UpiStatusBadge status={request.status} />
        </div>
        <p className="text-slate-700">
          <strong>{formatMoney(request.amount)}</strong> · {request.purpose === "renewal" ? "Renewal" : "New membership"} · {request.plan.name}
          {request.seat ? ` · seat ${request.seat.label}` : ""}
        </p>
        <p className="text-sm text-slate-600">
          UTR <span className="font-mono">{request.utr}</span> · sent {formatDateTime(request.created_at)}
        </p>
        {request.status === "pending" && (
          <p className={request.overdue ? "text-sm font-medium text-red-700" : "text-sm text-slate-600"}>
            {request.overdue
              ? `Waiting ${waitingText(request.waiting_hours)}: the student is waiting for your decision. Please approve or reject it.`
              : `Waiting ${waitingText(request.waiting_hours)}`}
          </p>
        )}
        {request.student_note && <p className="text-sm text-slate-700">Student&apos;s note: {request.student_note}</p>}
        {request.status === "rejected" && <p className="text-sm text-slate-700">Rejected: {request.review_note}</p>}
        {request.reviewed_at && (
          <p className="text-sm text-slate-600">
            Decided by {request.reviewed_by ?? "you"} on {formatDateTime(request.reviewed_at)}
            {request.receipt_number ? ` · receipt ${request.receipt_number}` : ""}
          </p>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          {request.has_screenshot && (
            <Button variant="secondary" size="sm" onClick={onScreenshot}>
              View screenshot
            </Button>
          )}
          {request.status === "pending" && (
            <>
              <Button size="sm" onClick={onApprove}>
                Approve
              </Button>
              <Button size="sm" variant="secondary" onClick={onReject}>
                Reject
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/** `/owner/payments/upi`: payments students say they made directly to you, waiting for your decision. */
export function UpiRequestsScreen() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [approving, setApproving] = useState<OwnerUpiRequest | null>(null);
  const [rejecting, setRejecting] = useState<OwnerUpiRequest | null>(null);
  const [viewing, setViewing] = useState<OwnerUpiRequest | null>(null);
  const [rejectError, setRejectError] = useState<string | null>(null);
  const filters = { status: status === "any" ? undefined : (status as UpiRequestStatus), page };
  const query = useQuery({
    queryKey: queryKeys.ownerUpiRequests(filters),
    queryFn: () => fetchOwnerUpiRequests(filters),
    placeholderData: (previous) => previous,
  });

  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectUpiRequest(id, reason),
    onSuccess: async () => {
      setRejecting(null);
      setRejectError(null);
      await queryClient.invalidateQueries({ queryKey: ["owner"] });
      toast.success("Request rejected. The student has been told.");
    },
    onError: (failure) => setRejectError(userMessage(failure)),
  });

  return (
    <Page className="max-w-3xl">
      <PageHeader
        title="Payments to check"
        description="Students who paid you by UPI. Look for the payment in your own UPI or bank history, then approve or reject."
        actions={
          <Button asChild variant="secondary">
            <Link href="/owner/payments/upi/settings">UPI settings</Link>
          </Button>
        }
      />
      <FormField label="Show" className="sm:w-60">
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          options={STATUS_OPTIONS}
        />
      </FormField>
      {query.isPending ? (
        <LoadingList label="Loading payment requests" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load the payment requests." />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          title={status === "pending" ? "Nothing to check" : "No requests here"}
          description={status === "pending" ? "When a student sends a payment reference, it will appear here." : "Try another filter."}
        />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {query.data.items.map((request) => (
              <li key={request.id}>
                <RequestCard
                  request={request}
                  onApprove={() => setApproving(request)}
                  onReject={() => {
                    setRejectError(null);
                    setRejecting(request);
                  }}
                  onScreenshot={() => setViewing(request)}
                />
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPageChange={setPage} />
        </>
      )}
      {approving && <ApproveDialog request={approving} onClose={() => setApproving(null)} />}
      {viewing && <ScreenshotDialog request={viewing} onClose={() => setViewing(null)} />}
      <ReasonDialog
        key={rejecting?.id ?? "none"}
        open={rejecting !== null}
        onOpenChange={(open) => !open && setRejecting(null)}
        title={rejecting ? `Reject the payment from ${rejecting.student.name}?` : "Reject"}
        description="The student is told your reason. Nothing is activated. If they really paid, you must refund them yourself: LibraryHive cannot return UPI money."
        confirmLabel="Reject payment"
        destructive
        maxLength={300}
        loading={reject.isPending}
        error={rejectError}
        onSubmit={(reason) => rejecting && reject.mutate({ id: rejecting.id, reason })}
      />
    </Page>
  );
}
