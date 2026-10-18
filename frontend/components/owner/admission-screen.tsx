"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { OFFLINE_METHOD_OPTIONS } from "@/components/owner/record-renewal-dialog";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { DateField, Input, PhoneField } from "@/components/ui/input";
import { Breadcrumbs } from "@/components/ui/navigation";
import { Page, PageHeader } from "@/components/ui/page";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { Alert } from "@/components/ui/surface";
import { fetchDomains, fetchOwnerPlans } from "@/lib/api/libraries";
import { admitStudent, lookupAdmission } from "@/lib/api/memberships";
import { fetchOwnerSeats } from "@/lib/api/seats";
import { isApiError, userMessage } from "@/lib/errors";
import { applyServerError } from "@/lib/forms";
import { formatDate, formatMoney } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import { admissionSchema, type AdmissionValues } from "@/lib/schemas/admission";
import type { AdmissionLookup, AdmissionResult } from "@/lib/types";

const FIELDS = ["name", "phone", "email", "domain_code", "seat_id", "plan_id", "start_date", "method", "notes"] as const;

type LookupState = { kind: "idle" } | { kind: "checking" } | { kind: "done"; result: AdmissionLookup } | { kind: "blocked"; message: string };

function LookupNote({ state }: { state: LookupState }) {
  if (state.kind === "blocked") return <Alert tone="danger">{state.message}</Alert>;
  if (state.kind !== "done") return null;
  const { result } = state;
  if (result.match === "none") {
    return <Alert tone="info">No account uses this phone number or email, so a new student record will be created.</Alert>;
  }
  const student = result.student;
  if (!student) return null;
  const contact = [student.masked_phone, student.masked_email].filter(Boolean).join(" · ");
  return student.is_member_here ? (
    <Alert tone="danger" title="Already a member here">
      {student.name} ({contact}) already has a seat in your library, so they can&apos;t be admitted again.
    </Alert>
  ) : (
    <Alert tone="warning" title="This student already has an account">
      {student.name} ({contact}) will be linked to this admission. Check that this is the right person.
    </Alert>
  );
}

/** `/owner/members/new`: admit a walk-in student with a seat, a plan and the payment they made (T15, #53, #54). */
export function AdmissionScreen({ initialSeatId }: { initialSeatId?: string }) {
  const queryClient = useQueryClient();
  const [lookup, setLookup] = useState<LookupState>({ kind: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState<AdmissionResult | null>(null);

  const seats = useQuery({ queryKey: queryKeys.ownerSeats, queryFn: () => fetchOwnerSeats() });
  const plans = useQuery({ queryKey: queryKeys.ownerPlans, queryFn: fetchOwnerPlans });
  const domains = useQuery({ queryKey: queryKeys.domains, queryFn: fetchDomains });

  const {
    register,
    control,
    handleSubmit,
    getValues,
    setError,
    reset,
    formState: { errors },
  } = useForm<AdmissionValues>({
    resolver: zodResolver(admissionSchema),
    defaultValues: {
      name: "",
      phone: "",
      email: "",
      domain_code: "",
      seat_id: initialSeatId ?? "",
      plan_id: "",
      start_date: "",
      method: "cash",
      notes: "",
    },
    mode: "onTouched",
  });

  const watchedPlan = useWatch({ control, name: "plan_id" });

  const admit = useMutation({
    mutationFn: (values: AdmissionValues) =>
      admitStudent({
        student: {
          name: values.name,
          phone: values.phone,
          ...(values.email ? { email: values.email } : {}),
          ...(values.domain_code ? { domain_code: values.domain_code } : {}),
        },
        seat_id: values.seat_id,
        plan_id: values.plan_id,
        ...(values.start_date ? { start_date: values.start_date } : {}),
        payment: { method: values.method, ...(values.notes ? { notes: values.notes } : {}) },
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["owner"] });
      setDone(result);
    },
    onError: (error) =>
      setFormError(
        applyServerError(error, setError, FIELDS, {
          PLAN_INACTIVE: "plan_id",
          SEAT_UNAVAILABLE: "seat_id",
        }),
      ),
  });

  async function check() {
    const { phone, email } = getValues();
    if (!admissionSchema.shape.phone.safeParse(phone).success) {
      setError("phone", { type: "validate", message: "Enter a valid Indian mobile number." }, { shouldFocus: true });
      return;
    }
    setLookup({ kind: "checking" });
    try {
      setLookup({ kind: "done", result: await lookupAdmission({ phone, ...(email.trim() ? { email: email.trim() } : {}) }) });
    } catch (error) {
      setLookup(isApiError(error, "IDENTITY_CONFLICT") || isApiError(error, "CONFLICT") ? { kind: "blocked", message: userMessage(error) } : { kind: "idle" });
      if (!(isApiError(error, "IDENTITY_CONFLICT") || isApiError(error, "CONFLICT"))) setFormError(userMessage(error));
    }
  }

  if (done) {
    return (
      <Page className="max-w-2xl">
        <div role="status" className="flex flex-col items-start gap-3 rounded-xl border border-emerald-300 bg-emerald-50 p-6">
          <CheckCircle2 aria-hidden="true" className="size-8 text-emerald-700" />
          <h1 className="text-xl font-semibold text-emerald-900">{done.student.name} is admitted</h1>
          <p className="text-emerald-900">
            Seat {done.membership.seat.label} · valid until {formatDate(done.membership.next_due_date)} · receipt {done.payment.receipt_number} ·{" "}
            {formatMoney(done.payment.amount)}
          </p>
          <p className="text-sm text-emerald-900">
            {done.student.created
              ? "A student record was created for them. They can sign up later with the same phone number to claim it."
              : "This student already had an account, which now has this membership."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href={`/owner/members/${done.membership.membership_id}`}>View member</Link>
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setDone(null);
                setLookup({ kind: "idle" });
                reset();
              }}
            >
              Admit another student
            </Button>
          </div>
        </div>
      </Page>
    );
  }

  const freeSeats = (seats.data?.seats ?? []).filter(
    (seat) => seat.status === "empty" || (seat.status === "reserved" && seat.hold?.kind === "owner_manual"),
  );
  const activePlans = (plans.data ?? []).filter((plan) => plan.is_active);
  const selectedPlan = activePlans.find((plan) => plan.id === watchedPlan);
  const loading = seats.isPending || plans.isPending;
  const loadFailed = seats.isError || plans.isError;

  return (
    <Page className="max-w-2xl">
      <Breadcrumbs items={[{ label: "Members", href: "/owner/members" }, { label: "Admit a student" }]} />
      <PageHeader
        title="Admit a student"
        description="For a student who walked in. You'll record their seat, plan and the payment they made. They don't need an account."
      />

      {loadFailed ? (
        <ErrorState error={seats.error ?? plans.error} onRetry={() => { void seats.refetch(); void plans.refetch(); }} title="We couldn't load your seats and plans." />
      ) : loading ? (
        <div aria-busy="true" className="flex flex-col gap-3">
          <span className="sr-only" role="status">
            Loading
          </span>
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : (
        <form onSubmit={handleSubmit((values) => { setFormError(null); admit.mutate(values); })} noValidate className="flex flex-col gap-6">
          <fieldset className="flex flex-col gap-4">
            <legend className="mb-1 text-lg font-semibold text-slate-900">Student</legend>
            <FormField label="Full name" required error={errors.name?.message}>
              <Input autoComplete="off" {...register("name")} />
            </FormField>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Mobile number" required error={errors.phone?.message}>
                <PhoneField {...register("phone", { onChange: () => setLookup({ kind: "idle" }) })} />
              </FormField>
              <FormField label="Email" hint="Optional." error={errors.email?.message}>
                <Input type="email" autoComplete="off" {...register("email", { onChange: () => setLookup({ kind: "idle" }) })} />
              </FormField>
            </div>
            <div className="flex flex-col items-start gap-3">
              <Button variant="secondary" loading={lookup.kind === "checking"} onClick={() => void check()}>
                Check if they already have an account
              </Button>
              <LookupNote state={lookup} />
            </div>
            <Controller
              control={control}
              name="domain_code"
              render={({ field }) => (
                <FormField label="Exam they are preparing for" hint="Optional." error={errors.domain_code?.message}>
                  <Select
                    value={field.value || "none"}
                    onValueChange={(value) => field.onChange(value === "none" ? "" : value)}
                    options={[{ value: "none", label: "Not specified" }, ...(domains.data ?? []).map((d) => ({ value: d.code, label: d.name }))]}
                  />
                </FormField>
              )}
            />
          </fieldset>

          <fieldset className="flex flex-col gap-4">
            <legend className="mb-1 text-lg font-semibold text-slate-900">Seat and plan</legend>
            <Controller
              control={control}
              name="seat_id"
              render={({ field }) => (
                <FormField
                  label="Seat"
                  required
                  error={errors.seat_id?.message}
                  hint={freeSeats.length === 0 ? "You have no free seats. Add seats or archive a member first." : undefined}
                >
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    placeholder="Choose a free seat"
                    options={freeSeats.map((seat) => ({ value: seat.id, label: seat.status === "reserved" ? `${seat.label} (blocked by you)` : seat.label }))}
                  />
                </FormField>
              )}
            />
            <Controller
              control={control}
              name="plan_id"
              render={({ field }) => (
                <FormField label="Plan" required error={errors.plan_id?.message}>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    placeholder="Choose a plan"
                    options={activePlans.map((plan) => ({ value: plan.id, label: `${plan.name} · ${formatMoney(plan.price)} · ${plan.duration_days} days` }))}
                  />
                </FormField>
              )}
            />
            <FormField label="Start date" hint="Optional. Today if left empty; up to 30 days either way." error={errors.start_date?.message}>
              <DateField {...register("start_date")} />
            </FormField>
          </fieldset>

          <fieldset className="flex flex-col gap-4">
            <legend className="mb-1 text-lg font-semibold text-slate-900">Payment received</legend>
            <Controller
              control={control}
              name="method"
              render={({ field }) => (
                <FormField label="Paid by" required error={errors.method?.message}>
                  <Select value={field.value} onValueChange={field.onChange} options={OFFLINE_METHOD_OPTIONS} />
                </FormField>
              )}
            />
            <FormField label="Note" hint="Optional, for example a UPI reference." error={errors.notes?.message}>
              <Input {...register("notes")} />
            </FormField>
            {selectedPlan && (
              <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-800">
                Amount to record: <strong>{formatMoney(selectedPlan.price)}</strong> — taken from the plan.
              </p>
            )}
          </fieldset>

          {formError && <Alert tone="danger">{formError}</Alert>}
          <div className="flex gap-2">
            <Button type="submit" size="lg" loading={admit.isPending} disabled={lookup.kind === "blocked" || (lookup.kind === "done" && lookup.result.student?.is_member_here === true)}>
              Admit student and record payment
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/owner/members">Cancel</Link>
            </Button>
          </div>
        </form>
      )}
    </Page>
  );
}
