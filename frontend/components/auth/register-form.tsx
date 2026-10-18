"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { Button, buttonClasses } from "@/components/ui/button";
import { RadioCardGroup } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { Input, PhoneField } from "@/components/ui/input";
import { Alert } from "@/components/ui/surface";
import { useAuth } from "@/lib/auth-context";
import { isApiError } from "@/lib/errors";
import { applyServerError } from "@/lib/forms";
import { homeFor } from "@/lib/navigation";
import { PASSWORD_HINT, registerSchema, type RegisterValues } from "@/lib/schemas/auth";

import { AuthCard } from "./auth-card";
import { DomainSelect } from "./domain-select";
import { PasswordInput } from "./password-input";
import { useRedirectWhenSignedIn } from "./use-redirect-when-signed-in";

const FIELDS = ["role", "name", "email", "phone", "password", "domain_code"] as const;

interface ClaimRequired {
  phone: string;
  channels: string[];
  maskedEmail: string | null;
}

/** What the CLAIM_REQUIRED error carries (BACKEND_ARCHITECTURE.md #6, T04 notes). */
function readClaimRequired(error: unknown, phone: string): ClaimRequired | null {
  if (!isApiError(error, "CLAIM_REQUIRED")) return null;
  const details = (error.details ?? {}) as { channels?: unknown; masked_email?: unknown };
  const channels = Array.isArray(details.channels) ? details.channels.map(String) : ["owner_code"];
  return { phone, channels, maskedEmail: typeof details.masked_email === "string" ? details.masked_email : null };
}

/** Register with a Student / Owner switch (UI_ARCHITECTURE.md 6). */
export function RegisterForm() {
  const { register: signUp, user } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const [claim, setClaim] = useState<ClaimRequired | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    mode: "onBlur",
    defaultValues: { role: "student", domain_code: "" },
  });
  const role = useWatch({ control, name: "role" });

  const redirecting = useRedirectWhenSignedIn(user ? homeFor(user.role) : null);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    setClaim(null);
    try {
      await signUp({
        role: values.role,
        name: values.name,
        email: values.email,
        phone: values.phone,
        password: values.password,
        ...(values.role === "student" && values.domain_code ? { domain_code: values.domain_code } : {}),
      });
    } catch (error) {
      const claimRequired = readClaimRequired(error, values.phone);
      if (claimRequired) {
        setClaim(claimRequired);
        return;
      }
      setFormError(
        applyServerError(error, setError, FIELDS, {
          EMAIL_TAKEN: "email",
          PHONE_TAKEN: "phone",
        }),
      );
    }
  });

  if (claim) return <ClaimPanel claim={claim} onBack={() => setClaim(null)} />;

  return (
    <AuthCard
      title="Create your account"
      description="Find a library and a seat, or list your library for students."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-blue-700 hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <Controller
          control={control}
          name="role"
          render={({ field }) => (
            <RadioCardGroup
              label="I am a"
              value={field.value}
              onValueChange={field.onChange}
              className="grid-cols-2"
              options={[
                { value: "student", title: "Student" },
                { value: "owner", title: "Library owner" },
              ]}
            />
          )}
        />
        <FormField label="Full name" required error={errors.name?.message}>
          <Input autoComplete="name" {...register("name")} />
        </FormField>
        <FormField label="Email" required error={errors.email?.message}>
          <Input type="email" autoComplete="email" inputMode="email" {...register("email")} />
        </FormField>
        <FormField label="Mobile number" required hint="Indian mobile number (+91)." error={errors.phone?.message}>
          <PhoneField {...register("phone")} />
        </FormField>
        <FormField label="Password" required hint={PASSWORD_HINT} error={errors.password?.message}>
          <PasswordInput autoComplete="new-password" {...register("password")} />
        </FormField>
        {role === "student" && (
          <Controller
            control={control}
            name="domain_code"
            render={({ field }) => (
              <DomainSelect value={field.value} onChange={field.onChange} error={errors.domain_code?.message} />
            )}
          />
        )}
        {formError && <Alert tone="danger">{formError}</Alert>}
        <Button type="submit" fullWidth loading={isSubmitting || redirecting}>
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}

/** Shown instead of the form when a library has already added this person (never auto-linked). */
function ClaimPanel({ claim, onBack }: { claim: ClaimRequired; onBack: () => void }) {
  const hasEmailCode = claim.channels.includes("email_otp");
  const href = `/claim?phone=${encodeURIComponent(claim.phone)}`;
  return (
    <AuthCard title="Link your membership">
      <Alert tone="info" title="A library already added you as a member.">
        Verify it&apos;s you to link your account.{" "}
        {hasEmailCode && claim.maskedEmail
          ? `We can email a code to ${claim.maskedEmail}, or you can use a code from your library.`
          : "Ask your library for a claim code."}
      </Alert>
      <div className="flex flex-col gap-3">
        <Link href={href} className={buttonClasses("primary", "md", true)}>
          Verify and link my account
        </Link>
        <Button variant="ghost" fullWidth onClick={onBack}>
          Back to sign up
        </Button>
      </div>
    </AuthCard>
  );
}
