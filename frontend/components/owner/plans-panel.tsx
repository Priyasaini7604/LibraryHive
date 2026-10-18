"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Badge, Card, CardContent } from "@/components/ui/surface";
import { createPlan, fetchOwnerPlans, setPlanActive, updatePlan } from "@/lib/api/libraries";
import { userMessage } from "@/lib/errors";
import { applyServerError } from "@/lib/forms";
import { formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import { planSchema, type PlanValues } from "@/lib/schemas/library";
import type { OwnerPlan } from "@/lib/types";

const FIELDS = ["name", "duration_days", "price", "timing_note"] as const;

function PlanDialog({ plan, open, onOpenChange }: { plan: OwnerPlan | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<PlanValues>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      name: plan?.name ?? "",
      duration_days: plan ? String(plan.duration_days) : "",
      price: plan?.price ?? "",
      timing_note: plan?.timing_note ?? "",
    },
    mode: "onTouched",
  });

  const save = useMutation({
    mutationFn: (values: PlanValues) => {
      const input = { ...values, duration_days: Number(values.duration_days) };
      return plan ? updatePlan(plan.id, input) : createPlan(input);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.ownerPlans }),
        queryClient.invalidateQueries({ queryKey: queryKeys.ownerLibrary, exact: true }),
      ]);
      toast.success(plan ? "Plan updated." : "Plan added.");
      reset();
      onOpenChange(false);
    },
    onError: (error) => setFormError(applyServerError(error, setError, FIELDS, { PLAN_NAME_TAKEN: "name" })),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={plan ? "Edit plan" : "Add a plan"}
        description={plan ? "Changes apply to future periods only; past payments keep their amounts." : "Seats are sold for the full day; the timing note is for information only."}
      >
        <form onSubmit={handleSubmit((values) => save.mutate(values))} noValidate className="flex flex-col gap-4">
          <FormField label="Plan name" required error={errors.name?.message}>
            <Input {...register("name")} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Duration (days)" required error={errors.duration_days?.message}>
              <Input inputMode="numeric" {...register("duration_days")} />
            </FormField>
            <FormField label="Price (₹)" required error={errors.price?.message}>
              <Input inputMode="decimal" {...register("price")} />
            </FormField>
          </div>
          <FormField label="Timing note" hint="Optional, for example 6 AM – 2 PM." error={errors.timing_note?.message}>
            <Input {...register("timing_note")} />
          </FormField>
          {formError && <Alert tone="danger">{formError}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending}>
              {plan ? "Save plan" : "Add plan"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Pricing plans (#20-#24). A plan in use can only be deactivated, never deleted. */
export function PlansPanel() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<OwnerPlan | null>(null);
  const [adding, setAdding] = useState(false);
  const plans = useQuery({ queryKey: queryKeys.ownerPlans, queryFn: fetchOwnerPlans });

  const toggle = useMutation({
    mutationFn: (plan: OwnerPlan) => setPlanActive(plan.id, !plan.is_active),
    onSuccess: async (plan) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.ownerPlans }),
        queryClient.invalidateQueries({ queryKey: queryKeys.ownerLibrary, exact: true }),
      ]);
      toast.success(plan.is_active ? "Plan is available for booking again." : "Plan hidden from booking.");
    },
    onError: (error) => toast.error(userMessage(error)),
  });

  return (
    <section aria-labelledby="plans-heading" className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id="plans-heading" className="text-lg font-semibold text-slate-900">
          Plans
        </h2>
        <Button size="sm" onClick={() => setAdding(true)}>
          <Plus aria-hidden="true" className="size-4" /> Add plan
        </Button>
      </div>

      {plans.isPending ? (
        <div aria-busy="true" className="flex flex-col gap-3">
          <span className="sr-only" role="status">
            Loading plans
          </span>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : plans.isError ? (
        <ErrorState error={plans.error} onRetry={() => void plans.refetch()} title="We couldn't load your plans." />
      ) : plans.data.length === 0 ? (
        <EmptyState
          title="No plans yet"
          description="Add at least one plan so students can book a seat. Nothing is pre-filled for you."
          action={<Button onClick={() => setAdding(true)}>Add your first plan</Button>}
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {plans.data.map((plan) => (
            <li key={plan.id}>
              <Card>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-4">
                  <div className="flex flex-col gap-0.5">
                    <p className="flex items-center gap-2 font-medium text-slate-900">
                      {plan.name}
                      {!plan.is_active && <Badge>Hidden</Badge>}
                    </p>
                    <p className="text-sm text-slate-700">
                      {formatMoney(plan.price)} · {plan.duration_days} days
                      {plan.timing_note && ` · ${plan.timing_note}`}
                    </p>
                    {plan.in_use && <p className="text-xs text-slate-600">In use by members, so it can be hidden but not removed.</p>}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" aria-label={`Edit ${plan.name}`} onClick={() => setEditing(plan)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      aria-label={`${plan.is_active ? "Hide" : "Show"} ${plan.name}`}
                      loading={toggle.isPending && toggle.variables?.id === plan.id}
                      onClick={() => toggle.mutate(plan)}
                    >
                      {plan.is_active ? "Hide" : "Show"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {adding && <PlanDialog key="add" plan={null} open onOpenChange={setAdding} />}
      {editing && <PlanDialog key={editing.id} plan={editing} open onOpenChange={(open) => !open && setEditing(null)} />}
    </section>
  );
}
