"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { Input, Textarea } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/overlay";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { ErrorState } from "@/components/ui/states";
import { Alert, Card, CardContent, CardTitle } from "@/components/ui/surface";
import { fetchUpiSettings, removeUpiQr, saveUpiSettings, uploadUpiQr } from "@/lib/api/upi";
import { userMessage } from "@/lib/errors";
import { queryKeys } from "@/lib/query-keys";
import type { UpiPaymentSettings } from "@/lib/types";

const UPI_ID_PATTERN = /^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9]{1,31}$/;
const MAX_QR_BYTES = 5 * 1024 * 1024;

function SettingsForm({ settings }: { settings: UpiPaymentSettings }) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(settings.upi_enabled);
  const [upiId, setUpiId] = useState(settings.upi_id);
  const [instructions, setInstructions] = useState(settings.instructions);
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const idError = upiId.trim() && !UPI_ID_PATTERN.test(upiId.trim()) ? "Enter a valid UPI ID, for example name@bank." : undefined;
  const needsTarget = enabled && !upiId.trim() && !settings.has_qr ? "Upload your QR code or enter your UPI ID first." : undefined;

  const save = useMutation({
    mutationFn: () => saveUpiSettings({ upi_enabled: enabled, upi_id: upiId.trim(), instructions: instructions.trim() }),
    onSuccess: async (saved) => {
      queryClient.setQueryData(queryKeys.ownerUpiSettings, saved);
      toast.success("Payment settings saved.");
    },
    onError: (failure) => setError(userMessage(failure)),
  });

  return (
    <Card aria-label="UPI payment settings">
      <CardContent className="flex flex-col gap-4 pt-4">
        <CardTitle>Your UPI details</CardTitle>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            setTouched(true);
            setError(null);
            if (!idError && !needsTarget) save.mutate();
          }}
        >
          <FormField label="UPI ID" hint="Students can type this if they cannot scan the code." error={touched ? idError : undefined}>
            <Input value={upiId} onChange={(event) => setUpiId(event.target.value)} autoComplete="off" maxLength={100} placeholder="name@bank" />
          </FormField>
          <FormField label="Instructions for students (optional)" hint="For example: write your name in the payment note. Plain text only.">
            <Textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} maxLength={1000} rows={3} />
          </FormField>
          <Checkbox label="Accept UPI payments from students" checked={enabled} onCheckedChange={setEnabled} />
          {touched && needsTarget && <Alert tone="danger">{needsTarget}</Alert>}
          {error && <Alert tone="danger">{error}</Alert>}
          <Button type="submit" loading={save.isPending} className="self-start">
            Save settings
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function QrCard({ settings }: { settings: UpiPaymentSettings }) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async (next: UpiPaymentSettings) => {
    queryClient.setQueryData(queryKeys.ownerUpiSettings, next);
  };
  const upload = useMutation({
    mutationFn: (file: File) => uploadUpiQr(file),
    onSuccess: async (next) => {
      await refresh(next);
      toast.success("QR code saved.");
    },
    onError: (failure) => setError(userMessage(failure)),
  });
  const remove = useMutation({
    mutationFn: removeUpiQr,
    onSuccess: async (next) => {
      setConfirmingRemove(false);
      await refresh(next);
      toast.success("QR code removed.");
    },
    onError: (failure) => {
      setConfirmingRemove(false);
      setError(userMessage(failure));
    },
  });

  const choose = (file: File | undefined) => {
    setError(null);
    if (!file) return;
    if (file.size > MAX_QR_BYTES) {
      setError("The image must be 5 MB or smaller.");
      return;
    }
    upload.mutate(file);
  };

  return (
    <Card aria-label="UPI QR code">
      <CardContent className="flex flex-col gap-4 pt-4">
        <CardTitle>Your QR code</CardTitle>
        <p className="text-sm text-slate-700">
          Upload the QR code from your UPI app (a screenshot or photo is fine). Students see it only while they are paying your library. Check that it scans
          after you save it.
        </p>
        {settings.qr_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- a short-lived signed link; next/image would cache it
          <img src={settings.qr_url} alt="Your saved UPI QR code" className="size-56 rounded-lg border border-slate-200 bg-white object-contain p-2" />
        ) : (
          <p className="text-sm text-slate-600">No QR code uploaded yet.</p>
        )}
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="flex flex-wrap gap-2">
          <input
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="sr-only"
            aria-label="Choose a QR code image"
            tabIndex={-1}
            onChange={(event) => {
              choose(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <Button variant="secondary" loading={upload.isPending} onClick={() => fileInput.current?.click()}>
            {settings.has_qr ? "Replace QR code" : "Upload QR code"}
          </Button>
          {settings.has_qr && (
            <Button variant="ghost" onClick={() => setConfirmingRemove(true)}>
              Remove QR code
            </Button>
          )}
        </div>
      </CardContent>
      <ConfirmDialog
        open={confirmingRemove}
        onOpenChange={setConfirmingRemove}
        title="Remove your QR code?"
        description="Students will no longer see it. They can still use your UPI ID if you added one."
        confirmLabel="Remove"
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </Card>
  );
}

/** `/owner/payments/upi/settings`: your UPI ID, instructions and QR code, and the on/off switch. */
export function UpiSettingsScreen() {
  const query = useQuery({ queryKey: queryKeys.ownerUpiSettings, queryFn: fetchUpiSettings });
  return (
    <Page className="max-w-2xl">
      <PageHeader
        title="UPI payments"
        description="Students pay you directly. LibraryHive never holds this money and does not take a commission."
        actions={
          <Button asChild variant="secondary">
            <Link href="/owner/payments/upi">Payments to check</Link>
          </Button>
        }
      />
      {query.isPending ? (
        <LoadingList label="Loading your payment settings" rows={2} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your payment settings." />
      ) : (
        <>
          <Alert tone="info" title="You confirm every payment yourself">
            When a student sends a payment reference, check your own UPI or bank history before you approve it. A screenshot is not proof of payment.
          </Alert>
          <SettingsForm key={`${query.data.upi_enabled}-${query.data.upi_id}-${query.data.instructions}`} settings={query.data} />
          <QrCard settings={query.data} />
        </>
      )}
    </Page>
  );
}
