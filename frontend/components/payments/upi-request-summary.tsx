import { StatusBadge, Card, CardContent, type Tone } from "@/components/ui/surface";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { StudentUpiRequest, UpiRequestStatus } from "@/lib/types";

/** "26 hours" or "3 days" for how long a request has waited. */
export function waitingText(hours: number | null): string {
  const h = hours ?? 0;
  return h >= 48 ? `${Math.floor(h / 24)} days` : `${h} hours`;
}

const STATUS: Record<UpiRequestStatus, { label: string; tone: Tone }> = {
  pending: { label: "Waiting for the library", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export function UpiStatusBadge({ status }: { status: UpiRequestStatus }) {
  const { label, tone } = STATUS[status];
  return <StatusBadge tone={tone} label={label} />;
}

/**
 * One payment request as the student sees it. A pending request says plainly that nothing is confirmed and that
 * the student can contact the library; a rejected or cancelled one never claims a refund.
 */
export function UpiRequestSummary({ request, actions }: { request: StudentUpiRequest; actions?: React.ReactNode }) {
  const { library } = request;
  return (
    <Card aria-label={`Payment request to ${library.name}`}>
      <CardContent className="flex flex-col gap-2 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-semibold text-slate-900">{library.name}</p>
          <UpiStatusBadge status={request.status} />
        </div>
        <p className="text-slate-700">
          {formatMoney(request.amount)} · {request.purpose === "renewal" ? "Renewal" : "New membership"} · {request.plan.name}
          {request.seat ? ` · seat ${request.seat.label}` : ""}
        </p>
        <p className="text-sm text-slate-600">
          UTR <span className="font-mono">{request.utr}</span> · sent {formatDateTime(request.created_at)}
        </p>
        {request.status === "pending" && request.overdue && (
          <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">
            Still waiting after {waitingText(request.waiting_hours)}. The library has not decided yet. Please contact them directly (details below). You can
            cancel this request if you did not pay or want to book elsewhere; cancelling does not return any money you already paid.
          </p>
        )}
        {request.status === "pending" && (
          <p className="text-sm text-slate-700">
            Not confirmed yet. If this takes long, contact the library directly
            {library.contact_phone ? ` on ${library.contact_phone}` : ""}
            {library.contact_email ? `${library.contact_phone ? " or " : " at "}${library.contact_email}` : ""}.
          </p>
        )}
        {request.status === "approved" && (
          <p className="text-sm text-slate-700">Approved{request.receipt_number ? `. Receipt ${request.receipt_number}.` : "."}</p>
        )}
        {request.status === "rejected" && (
          <p className="text-sm text-slate-700">
            The library could not confirm this payment{request.review_note ? `: ${request.review_note}` : "."} If you did pay, contact the library
            directly. LibraryHive does not refund UPI transfers.
            {library.contact_phone ? ` Phone: ${library.contact_phone}.` : ""}
          </p>
        )}
        {request.status === "cancelled" && <p className="text-sm text-slate-700">You cancelled this request. Nothing was activated.</p>}
        {actions}
      </CardContent>
    </Card>
  );
}
