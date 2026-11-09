"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";

import { UpiRequestSummary } from "@/components/payments/upi-request-summary";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input, Textarea } from "@/components/ui/input";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Card, CardContent, CardTitle } from "@/components/ui/surface";
import { fetchUpiInfo, submitUpiRequest } from "@/lib/api/upi";
import { isApiError, userMessage } from "@/lib/errors";
import { formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { StudentUpiRequest, UpiSource } from "@/lib/types";

const MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024;
/** A QR link that fails to load is asked for again at most this many times, then the student is told. */
export const MAX_QR_RELOADS = 2;
const UTR_PATTERN = /^[A-Za-z0-9]{10,30}$/;

/** The UTR as the server will read it: spaces removed. */
export function cleanUtr(raw: string): string {
  return raw.replace(/\s+/g, "");
}

/**
 * Pay the library directly by UPI, then tell the library the reference number (UTR).
 *
 * Nothing here confirms a payment: the owner checks their own UPI or bank history and approves. The amount shown
 * is only for display; the server takes the amount, plan and library from the booking, never from this form.
 */
export function UpiPayPanel({
  libraryId,
  source,
  amount,
  holdNote,
}: {
  libraryId: string;
  source: UpiSource;
  amount: string;
  /** For a new booking: what happens to the seat while the owner checks. */
  holdNote?: string;
}) {
  const queryClient = useQueryClient();
  const info = useQuery({
    queryKey: queryKeys.studentUpiInfo(libraryId),
    queryFn: () => fetchUpiInfo(libraryId),
    // The QR link is signed for 10 minutes; ask again before it lapses.
    refetchInterval: 8 * 60_000,
  });
  const [utr, setUtr] = useState("");
  const [note, setNote] = useState("");
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [touched, setTouched] = useState(false);
  const [sent, setSent] = useState<StudentUpiRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const qrReloads = useRef(0);
  const [qrBroken, setQrBroken] = useState(false);

  const utrError = !UTR_PATTERN.test(cleanUtr(utr)) ? "Enter the reference (UTR) exactly as your UPI app shows it, 10 to 30 letters and digits." : undefined;
  const shotError = screenshot && screenshot.size > MAX_SCREENSHOT_BYTES ? "The screenshot must be 5 MB or smaller." : undefined;

  const send = useMutation({
    mutationFn: () => submitUpiRequest(source, { utr: cleanUtr(utr), note: note.trim(), screenshot }),
    onSuccess: async (request) => {
      setSent(request);
      await queryClient.invalidateQueries({ queryKey: ["student"] });
    },
    onError: (failure) => setError(userMessage(failure)),
  });

  if (sent) {
    return (
      <div className="flex flex-col gap-3">
        <Alert tone="success" title="Request sent to the library">
          Your payment is <strong>not confirmed yet</strong>. The library owner will check their UPI or bank history and approve it.
          {holdNote ? ` ${holdNote}` : ""}
        </Alert>
        <UpiRequestSummary request={sent} />
        <Button asChild variant="secondary" className="self-start">
          <Link href="/student/payments/upi">See all my payment requests</Link>
        </Button>
      </div>
    );
  }

  if (info.isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-3">
        <span className="sr-only" role="status">
          Loading the payment details
        </span>
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }
  if (info.isError) {
    const unavailable = isApiError(info.error, "NOT_FOUND");
    return (
      <ErrorState
        error={info.error}
        onRetry={unavailable ? undefined : () => void info.refetch()}
        title={unavailable ? "UPI payment isn't available for this booking." : "We couldn't load the payment details."}
      />
    );
  }

  const { library } = info.data;
  return (
    <div className="flex flex-col gap-4">
      <Card aria-label="Pay by UPI">
        <CardContent className="flex flex-col gap-3 pt-4">
          <CardTitle>1. Pay {formatMoney(amount)} to {library.name}</CardTitle>
          <p className="text-sm text-slate-700">
            Open any UPI app (Google Pay, PhonePe, Paytm, your bank app), scan the code or use the UPI ID, and pay exactly{" "}
            <strong>{formatMoney(amount)}</strong>. The money goes straight to the library, not to LibraryHive.
          </p>
          <div className="flex flex-col items-start gap-4 sm:flex-row">
            {info.data.qr_url && qrBroken ? (
              <div className="flex max-w-xs flex-col items-start gap-2">
                <Alert tone="warning" title="The QR code could not be loaded">
                  {info.data.upi_id ? "Pay using the UPI ID shown here, or try loading the code again." : "Try loading the code again, or contact the library."}
                </Alert>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    qrReloads.current = 0;
                    setQrBroken(false);
                    void info.refetch();
                  }}
                >
                  Load the QR code again
                </Button>
              </div>
            ) : info.data.qr_url ? (
              // eslint-disable-next-line @next/next/no-img-element -- a short-lived signed link; next/image would cache it
              <img
                src={info.data.qr_url}
                alt={`UPI QR code of ${library.name}`}
                className="size-56 rounded-lg border border-slate-200 bg-white object-contain p-2"
                onLoad={() => {
                  qrReloads.current = 0;
                }}
                onError={() => {
                  // The link may simply have expired, so ask for a fresh one, but never in a loop.
                  if (qrReloads.current < MAX_QR_RELOADS) {
                    qrReloads.current += 1;
                    void info.refetch();
                  } else {
                    setQrBroken(true);
                  }
                }}
              />
            ) : (
              <p className="text-sm text-slate-600">This library has not added a QR code. Use the UPI ID.</p>
            )}
            <dl className="flex flex-col gap-2 text-sm">
              {info.data.upi_id && (
                <div>
                  <dt className="text-slate-600">UPI ID</dt>
                  <dd className="font-mono text-base font-semibold text-slate-900">{info.data.upi_id}</dd>
                </div>
              )}
              {info.data.instructions && (
                <div>
                  <dt className="text-slate-600">Instructions from the library</dt>
                  <dd className="whitespace-pre-wrap text-slate-900">{info.data.instructions}</dd>
                </div>
              )}
            </dl>
          </div>
        </CardContent>
      </Card>

      <Card aria-label="Send the payment reference">
        <CardContent className="flex flex-col gap-4 pt-4">
          <CardTitle>2. Tell the library you paid</CardTitle>
          <Alert tone="warning" title="Sending this does not confirm your payment">
            The library owner checks their own UPI or bank history before approving. A UTR or a screenshot alone proves nothing.
          </Alert>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              setTouched(true);
              setError(null);
              if (!utrError && !shotError) send.mutate();
            }}
          >
            <FormField label="Transaction reference (UTR)" required hint="Shown in your UPI app after paying, also called UPI Ref No." error={touched ? utrError : undefined}>
              <Input value={utr} onChange={(event) => setUtr(event.target.value)} autoComplete="off" inputMode="text" maxLength={40} />
            </FormField>
            <FormField label="Payment screenshot (optional)" hint="JPG, PNG or WEBP, up to 5 MB. Only you and this library can see it." error={touched ? shotError : undefined}>
              <Input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setScreenshot(event.target.files?.[0] ?? null)} />
            </FormField>
            <FormField label="Note for the library (optional)">
              <Textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={300} rows={2} />
            </FormField>
            {error && <Alert tone="danger">{error}</Alert>}
            <Button type="submit" size="lg" loading={send.isPending} className="self-start">
              I have paid, send to the library
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
