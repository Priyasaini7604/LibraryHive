"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Alert } from "@/components/ui/surface";
import { fetchOwnerPlans } from "@/lib/api/libraries";
import { recordRenewal } from "@/lib/api/memberships";
import { userMessage } from "@/lib/errors";
import { formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { OfflineMethod } from "@/lib/types";

export const OFFLINE_METHOD_OPTIONS = [
  { value: "cash", label: "Cash" },
  { value: "upi_direct", label: "UPI (paid directly)" },
  { value: "bank_transfer", label: "Bank transfer" },
];

/**
 * Record a renewal the member paid at the desk (#48). The amount is the plan's price; the server computes
 * the new period and the receipt, so nothing here can change what is charged.
 */
export function RecordRenewalDialog({
  membershipId,
  studentName,
  currentPlanId,
  onClose,
}: {
  membershipId: string;
  studentName: string;
  currentPlanId?: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const plans = useQuery({ queryKey: queryKeys.ownerPlans, queryFn: fetchOwnerPlans });
  const [method, setMethod] = useState<OfflineMethod>("cash");
  const [planId, setPlanId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const activePlans = (plans.data ?? []).filter((plan) => plan.is_active || plan.id === currentPlanId);
  const chosen = planId ?? currentPlanId ?? activePlans[0]?.id ?? "";
  const plan = activePlans.find((item) => item.id === chosen);

  const save = useMutation({
    mutationFn: () =>
      recordRenewal(membershipId, {
        method,
        ...(chosen && chosen !== currentPlanId ? { plan_id: chosen } : {}),
        ...(notes.trim() ? { notes: notes.trim() } : {}),
      }),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["owner"] }),
      ]);
      toast.success(`Renewal recorded. Receipt ${result.payment.receipt_number}.`);
      onClose();
    },
    onError: (failure) => setError(userMessage(failure)),
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={`Record a renewal for ${studentName}`} description="Use this when the member paid you directly. The new period and receipt are created for you.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            setError(null);
            save.mutate();
          }}
        >
          <FormField label="Plan" required>
            <Select
              value={chosen}
              onValueChange={setPlanId}
              placeholder={plans.isPending ? "Loading plans…" : "Choose a plan"}
              options={activePlans.map((item) => ({ value: item.id, label: `${item.name} · ${formatMoney(item.price)} · ${item.duration_days} days` }))}
            />
          </FormField>
          <FormField label="Paid by" required>
            <Select value={method} onValueChange={(value) => setMethod(value as OfflineMethod)} options={OFFLINE_METHOD_OPTIONS} />
          </FormField>
          <FormField label="Note" hint="Optional, for example a UPI reference.">
            <Input value={notes} maxLength={500} onChange={(event) => setNotes(event.target.value)} />
          </FormField>
          {plan && (
            <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-800">
              Amount to record: <strong>{formatMoney(plan.price)}</strong>
            </p>
          )}
          {plans.isError && <Alert tone="danger">We couldn&apos;t load your plans. Close this window and try again.</Alert>}
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending} disabled={!plan}>
              Record renewal
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
