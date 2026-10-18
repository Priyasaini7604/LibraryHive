"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button, buttonClasses } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input, OtpField } from "@/components/ui/input";
import { Alert } from "@/components/ui/surface";
import { confirmPasswordReset } from "@/lib/api/auth";
import { applyServerError } from "@/lib/forms";
import { PASSWORD_HINT, resetPasswordSchema, type ResetPasswordValues } from "@/lib/schemas/auth";

import { AuthCard } from "./auth-card";
import { PasswordInput } from "./password-input";

const FIELDS = ["email", "code", "new_password", "confirm_password"] as const;

/** Reset password with the emailed code. The server signs out every device, so success sends the user to log in. */
export function ResetPasswordForm() {
  const initialEmail = useSearchParams().get("email") ?? "";
  const [done, setDone] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    mode: "onBlur",
    defaultValues: { email: initialEmail },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const result = await confirmPasswordReset({
        email: values.email,
        code: values.code,
        newPassword: values.new_password,
      });
      setDone(result.message);
    } catch (error) {
      setFormError(applyServerError(error, setError, FIELDS));
    }
  });

  if (done) {
    return (
      <AuthCard title="Password changed">
        <Alert tone="success">{done}</Alert>
        <Link href="/login" className={buttonClasses("primary", "md", true)}>
          Log in
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Set a new password"
      description="Enter the 6-digit code we emailed you and choose a new password."
      footer={
        <Link href="/forgot-password" className="font-medium text-blue-700 hover:underline">
          Send a new code
        </Link>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormField label="Email" required error={errors.email?.message}>
          <Input type="email" autoComplete="email" inputMode="email" {...register("email")} />
        </FormField>
        <FormField label="6-digit code" required error={errors.code?.message}>
          <OtpField {...register("code")} />
        </FormField>
        <FormField label="New password" required hint={PASSWORD_HINT} error={errors.new_password?.message}>
          <PasswordInput autoComplete="new-password" {...register("new_password")} />
        </FormField>
        <FormField label="Repeat new password" required error={errors.confirm_password?.message}>
          <PasswordInput autoComplete="new-password" {...register("confirm_password")} />
        </FormField>
        {formError && <Alert tone="danger">{formError}</Alert>}
        <Button type="submit" fullWidth loading={isSubmitting}>
          Change password
        </Button>
      </form>
    </AuthCard>
  );
}
