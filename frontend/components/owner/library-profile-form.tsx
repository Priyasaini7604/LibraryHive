"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LocateFixed } from "lucide-react";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input, Textarea } from "@/components/ui/input";
import { Alert } from "@/components/ui/surface";
import { createLibrary, fetchAmenities, fetchDomains, updateLibrary, type LibraryInput } from "@/lib/api/libraries";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/cn";
import { applyServerError } from "@/lib/forms";
import { queryKeys } from "@/lib/query-keys";
import { libraryProfileSchema, type LibraryProfileValues } from "@/lib/schemas/library";
import type { OwnerLibrary, Vocabulary } from "@/lib/types";

const FIELDS = [
  "name",
  "description",
  "address",
  "city",
  "area",
  "contact_phone",
  "contact_email",
  "opens_at",
  "closes_at",
  "operating_notes",
  "latitude",
  "longitude",
  "domain_codes",
  "amenity_codes",
] as const;

function toValues(library: OwnerLibrary | null): LibraryProfileValues {
  return {
    name: library?.name ?? "",
    description: library?.description ?? "",
    address: library?.address ?? "",
    city: library?.city ?? "",
    area: library?.area ?? "",
    contact_phone: library?.contact_phone ?? "",
    contact_email: library?.contact_email ?? "",
    opens_at: library?.opens_at?.slice(0, 5) ?? "",
    closes_at: library?.closes_at?.slice(0, 5) ?? "",
    operating_notes: library?.operating_notes ?? "",
    latitude: library?.latitude == null ? "" : String(library.latitude),
    longitude: library?.longitude == null ? "" : String(library.longitude),
    domain_codes: library?.domains.map((d) => d.code) ?? [],
    amenity_codes: library?.amenities.map((a) => a.code) ?? [],
  };
}

function toInput(values: LibraryProfileValues): LibraryInput {
  return {
    name: values.name,
    description: values.description,
    address: values.address,
    city: values.city,
    area: values.area,
    latitude: values.latitude === "" ? null : Number(values.latitude),
    longitude: values.longitude === "" ? null : Number(values.longitude),
    contact_phone: values.contact_phone,
    contact_email: values.contact_email,
    opens_at: values.opens_at || null,
    closes_at: values.closes_at || null,
    operating_notes: values.operating_notes,
    domain_codes: values.domain_codes,
    amenity_codes: values.amenity_codes,
  };
}

function ChipGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Vocabulary[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium text-slate-900">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const active = value.includes(option.code);
          return (
            <button
              key={option.code}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(active ? value.filter((code) => code !== option.code) : [...value, option.code])}
              className={cn(
                "h-9 rounded-full border px-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600",
                active ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300 bg-white text-slate-700 hover:border-slate-400",
              )}
            >
              {option.name}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

/**
 * Library profile (#17 create, #19 edit). With `library` null it creates the library
 * (onboarding step 1 reuses it); otherwise it edits. Every rule is re-checked by the server.
 */
export function LibraryProfileForm({ library }: { library: OwnerLibrary | null }) {
  const queryClient = useQueryClient();
  const { reloadUser } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const domains = useQuery({ queryKey: queryKeys.domains, queryFn: fetchDomains, staleTime: 60 * 60 * 1000 });
  const amenities = useQuery({ queryKey: queryKeys.amenities, queryFn: fetchAmenities, staleTime: 60 * 60 * 1000 });

  const form = useForm<LibraryProfileValues>({
    resolver: zodResolver(libraryProfileSchema),
    defaultValues: toValues(library),
    mode: "onTouched",
  });
  const {
    register,
    handleSubmit,
    control,
    setError,
    setValue,
    reset,
    formState: { errors, isDirty },
  } = form;

  // Warn before leaving with unsaved edits (UI_ARCHITECTURE.md 5.6).
  useEffect(() => {
    if (!isDirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [isDirty]);

  const save = useMutation({
    mutationFn: (values: LibraryProfileValues) =>
      library ? updateLibrary(toInput(values)) : createLibrary(toInput(values)),
    onSuccess: async (saved) => {
      setFormError(null);
      queryClient.setQueryData(queryKeys.ownerLibrary, saved);
      reset(toValues(saved));
      toast.success(library ? "Library details saved." : "Library created.");
      if (!library) await reloadUser();
    },
    onError: (error) => setFormError(applyServerError(error, setError, FIELDS, { LIBRARY_EXISTS: "name" })),
  });

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      setLocationMessage("Your browser can't share its location. Enter the coordinates by hand.");
      return;
    }
    setLocationMessage(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setValue("latitude", position.coords.latitude.toFixed(6), { shouldDirty: true, shouldValidate: true });
        setValue("longitude", position.coords.longitude.toFixed(6), { shouldDirty: true, shouldValidate: true });
      },
      () => setLocationMessage("We couldn't get your location. Allow location access, or enter the coordinates by hand."),
      { timeout: 10_000 },
    );
  };

  return (
    <form onSubmit={handleSubmit((values) => save.mutate(values))} noValidate className="flex max-w-2xl flex-col gap-5">
      <FormField label="Library name" required error={errors.name?.message}>
        <Input autoComplete="organization" {...register("name")} />
      </FormField>
      <FormField label="Description" hint="Optional. Tell students what makes your library a good place to study." error={errors.description?.message}>
        <Textarea rows={4} {...register("description")} />
      </FormField>
      <FormField label="Address" required error={errors.address?.message}>
        <Input autoComplete="street-address" {...register("address")} />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="City" required error={errors.city?.message}>
          <Input autoComplete="address-level2" {...register("city")} />
        </FormField>
        <FormField label="Area or locality" error={errors.area?.message}>
          <Input {...register("area")} />
        </FormField>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Contact phone" hint="Shown to students on your page." error={errors.contact_phone?.message}>
          <Input type="tel" inputMode="tel" autoComplete="tel" {...register("contact_phone")} />
        </FormField>
        <FormField label="Contact email" error={errors.contact_email?.message}>
          <Input type="email" autoComplete="email" {...register("contact_email")} />
        </FormField>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Opens at" error={errors.opens_at?.message}>
          <Input type="time" {...register("opens_at")} />
        </FormField>
        <FormField label="Closes at" error={errors.closes_at?.message}>
          <Input type="time" {...register("closes_at")} />
        </FormField>
      </div>
      <FormField label="Opening notes" hint="For example: Open 24×7 during exams." error={errors.operating_notes?.message}>
        <Input {...register("operating_notes")} />
      </FormField>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium text-slate-900">Location</legend>
        <p className="text-sm text-slate-600">Students find you by location, and your library cannot go live without it.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Latitude" error={errors.latitude?.message}>
            <Input inputMode="decimal" {...register("latitude")} />
          </FormField>
          <FormField label="Longitude" error={errors.longitude?.message}>
            <Input inputMode="decimal" {...register("longitude")} />
          </FormField>
        </div>
        <Button variant="secondary" size="sm" className="self-start" onClick={useMyLocation}>
          <LocateFixed aria-hidden="true" className="size-4" /> Use my current location
        </Button>
        {locationMessage && <Alert tone="warning">{locationMessage}</Alert>}
      </fieldset>

      <Controller
        control={control}
        name="domain_codes"
        render={({ field }) => (
          <ChipGroup label="Exams you cater to" options={domains.data ?? []} value={field.value} onChange={field.onChange} />
        )}
      />
      {domains.isError && (
        <Alert tone="warning" action={<Button size="sm" variant="secondary" onClick={() => void domains.refetch()}>Try again</Button>}>
          We couldn&apos;t load the exam list.
        </Alert>
      )}
      <Controller
        control={control}
        name="amenity_codes"
        render={({ field }) => (
          <ChipGroup label="Amenities" options={amenities.data ?? []} value={field.value} onChange={field.onChange} />
        )}
      />
      {amenities.isError && (
        <Alert tone="warning" action={<Button size="sm" variant="secondary" onClick={() => void amenities.refetch()}>Try again</Button>}>
          We couldn&apos;t load the amenity list.
        </Alert>
      )}

      {formError && <Alert tone="danger">{formError}</Alert>}
      <div>
        <Button type="submit" loading={save.isPending}>
          {library ? "Save changes" : "Create library"}
        </Button>
      </div>
    </form>
  );
}
