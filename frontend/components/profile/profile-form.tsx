"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { DomainSelect } from "@/components/auth/domain-select";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input, PhoneField } from "@/components/ui/input";
import { Alert, Avatar, Card, CardContent, CardHeader, CardTitle } from "@/components/ui/surface";
import { FullPageSkeleton } from "@/components/ui/states";
import { updateProfile } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth-context";
import { applyServerError } from "@/lib/forms";
import { profileSchema, type ProfileValues } from "@/lib/schemas/auth";

const FIELDS = ["name", "phone", "domain_code"] as const;

/** Profile for both roles (AUTH-05, AUTH-06). Email is shown but not editable; only students have an exam domain. */
export function ProfileForm() {
  const { user, setUser } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    mode: "onBlur",
    values: user ? { name: user.name, phone: user.phone, domain_code: user.domain?.code ?? "" } : undefined,
  });

  if (!user) return <FullPageSkeleton />;
  const isStudent = user.role === "student";

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const updated = await updateProfile({
        name: values.name,
        phone: values.phone,
        ...(isStudent ? { domain_code: values.domain_code || null } : {}),
      });
      setUser(updated);
      reset({ name: updated.name, phone: updated.phone, domain_code: updated.domain?.code ?? "" });
      toast.success("Profile updated");
    } catch (error) {
      setFormError(applyServerError(error, setError, FIELDS, { PHONE_TAKEN: "phone" }));
    }
  });

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-4 sm:p-8">
      <div className="flex items-center gap-4">
        <Avatar name={user.name} />
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Your profile</h1>
          <p className="text-sm text-slate-600">{isStudent ? "Student account" : "Library owner account"}</p>
        </div>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Personal details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
            <FormField label="Full name" required error={errors.name?.message}>
              <Input autoComplete="name" {...register("name")} />
            </FormField>
            <FormField label="Email" hint="Your email is your login and can't be changed here.">
              <Input type="email" value={user.email} readOnly disabled />
            </FormField>
            <FormField label="Mobile number" required hint="Indian mobile number (+91)." error={errors.phone?.message}>
              <PhoneField {...register("phone")} />
            </FormField>
            {isStudent && (
              <Controller
                control={control}
                name="domain_code"
                render={({ field }) => (
                  <DomainSelect value={field.value} onChange={field.onChange} error={errors.domain_code?.message} />
                )}
              />
            )}
            {formError && <Alert tone="danger">{formError}</Alert>}
            <div className="flex justify-end">
              <Button type="submit" loading={isSubmitting} disabled={!isDirty}>
                Save changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
