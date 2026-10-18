"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Button, buttonClasses } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/surface";
import { requestPasswordReset } from "@/lib/api/auth";
import { applyServerError } from "@/lib/forms";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/lib/schemas/auth";

import { AuthCard } from "./auth-card";

/** Client-side hint only; the server throttles for real (UI_ARCHITECTURE.md 6). */
export const RESEND_SECONDS = 60;

/** Forgot password: email only, and always the same neutral confirmation. */
export function ForgotPasswordForm() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [message, setMessage] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema), mode: "onBlur" });

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const timer = setTimeout(() => setSecondsLeft((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [secondsLeft]);

  const send = async (email: string) => {
    setFormError(null);
    try {
      const result = await requestPasswordReset(email);
      setMessage(result.message);
      setSentTo(email);
      setSecondsLeft(RESEND_SECONDS);
    } catch (error) {
      setFormError(applyServerError(error, setError, ["email"]));
    }
  };

  const onSubmit = handleSubmit((values) => send(values.email));

  if (sentTo) {
    return (
      <AuthCard title="Check your email">
        <Alert tone="success">{message}</Alert>
        <div className="flex flex-col gap-3">
          <Link href={`/reset-password?email=${encodeURIComponent(sentTo)}`} className={buttonClasses("primary", "md", true)}>
            Enter code
          </Link>
          <Button variant="secondary" fullWidth disabled={secondsLeft > 0} onClick={() => void send(sentTo)}>
            {secondsLeft > 0 ? `Send again in ${secondsLeft}s` : "Send the code again"}
          </Button>
          {formError && <Alert tone="danger">{formError}</Alert>}
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Forgot your password?"
      description="Enter your email and we'll send you a code to set a new one."
      footer={
        <Link href="/login" className="font-medium text-blue-700 hover:underline">
          Back to log in
        </Link>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormField label="Email" required error={errors.email?.message}>
          <Input type="email" autoComplete="email" inputMode="email" {...register("email")} />
        </FormField>
        {formError && <Alert tone="danger">{formError}</Alert>}
        <Button type="submit" fullWidth loading={isSubmitting}>
          Send code
        </Button>
      </form>
    </AuthCard>
  );
}
