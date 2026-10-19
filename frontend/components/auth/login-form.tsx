"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/surface";
import { useAuth } from "@/lib/auth-context";
import { applyServerError } from "@/lib/forms";
import { homeFor, safeNextPath } from "@/lib/navigation";
import { loginSchema, type LoginValues } from "@/lib/schemas/auth";

import { AuthCard } from "./auth-card";
import { PasswordInput } from "./password-input";
import { useRedirectWhenSignedIn } from "./use-redirect-when-signed-in";

const FIELDS = ["email", "password"] as const;

/** Login (UI_ARCHITECTURE.md 6). Honours ?next= for same-origin relative paths only. */
export function LoginForm() {
  const { login, user } = useAuth();
  const next = safeNextPath(useSearchParams().get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema), mode: "onBlur" });

  const redirecting = useRedirectWhenSignedIn(user ? (next ?? homeFor(user.role)) : null);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login(values.email, values.password);
    } catch (error) {
      setFormError(applyServerError(error, setError, FIELDS));
    }
  });

  return (
    <AuthCard
      title="Log in"
      description="Welcome back to LibraryHive."
      footer={
        <>
          New here?{" "}
          <Link href="/register" className="font-medium text-blue-700 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormField label="Email" required error={errors.email?.message}>
          <Input type="email" autoComplete="email" inputMode="email" {...register("email")} />
        </FormField>
        <FormField label="Password" required error={errors.password?.message}>
          <PasswordInput autoComplete="current-password" {...register("password")} />
        </FormField>
        <div className="-mt-2 text-right text-sm">
          <Link href="/forgot-password" className="font-medium text-blue-700 hover:underline">
            Forgot password?
          </Link>
        </div>
        {formError && <Alert tone="danger">{formError}</Alert>}
        <Button type="submit" fullWidth loading={isSubmitting || redirecting}>
          Log in
        </Button>
      </form>
    </AuthCard>
  );
}
