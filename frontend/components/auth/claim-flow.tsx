"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { RadioCardGroup } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { Input, OtpField, PhoneField } from "@/components/ui/input";
import { Alert } from "@/components/ui/surface";
import { startClaim } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth-context";
import { isApiError } from "@/lib/errors";
import { applyServerError } from "@/lib/forms";
import { PASSWORD_HINT, claimCompleteSchema, claimStartSchema, type ClaimCompleteValues, type ClaimStartValues } from "@/lib/schemas/auth";
import type { ClaimChannel } from "@/lib/types";

import { AuthCard } from "./auth-card";
import { PasswordInput } from "./password-input";
import { useRedirectWhenSignedIn } from "./use-redirect-when-signed-in";

const MEMBERSHIP_PATH = "/student/memberships";
const COMPLETE_FIELDS = ["code", "password", "email", "name"] as const;

/**
 * Claim an offline account (UI_ARCHITECTURE.md 6). Step 1 asks for the phone and how to prove it;
 * step 2 takes the code and a new password. The wording never confirms whether a record exists.
 */
export function ClaimFlow() {
  const params = useSearchParams();
  const [step, setStep] = useState<"start" | "complete">("start");
  const [phone, setPhone] = useState(params.get("phone") ?? "");
  const [channel, setChannel] = useState<ClaimChannel>("email_otp");
  const { user } = useAuth();
  useRedirectWhenSignedIn(user ? MEMBERSHIP_PATH : null);

  if (step === "start") {
    return (
      <StartStep
        initialPhone={phone}
        initialChannel={channel}
        onDone={(values) => {
          setPhone(values.phone);
          setChannel(values.channel);
          setStep("complete");
        }}
      />
    );
  }
  return <CompleteStep phone={phone} channel={channel} onBack={() => setStep("start")} />;
}

function StartStep({
  initialPhone,
  initialChannel,
  onDone,
}: {
  initialPhone: string;
  initialChannel: ClaimChannel;
  onDone: (values: ClaimStartValues) => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ClaimStartValues>({
    resolver: zodResolver(claimStartSchema),
    mode: "onBlur",
    defaultValues: { phone: initialPhone, channel: initialChannel },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      // The owner code is handed over in person, so there is nothing to send for it.
      if (values.channel === "email_otp") await startClaim({ phone: values.phone, channel: "email_otp" });
      onDone(values);
    } catch (error) {
      if (isApiError(error, "CLAIM_INVALID")) {
        // No email on file for this record: the student needs a code from the library instead.
        setValue("channel", "owner_code");
        setFormError(error.message);
        return;
      }
      setFormError(applyServerError(error, setError, ["phone", "channel"]));
    }
  });

  return (
    <AuthCard
      title="I'm already a member of a library"
      description="Link the membership your library created for you to your own login."
      footer={
        <>
          No membership yet?{" "}
          <Link href="/register" className="font-medium text-blue-700 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormField
          label="Mobile number"
          required
          hint="The number your library has for you."
          error={errors.phone?.message}
        >
          <PhoneField {...register("phone")} />
        </FormField>
        <Controller
          control={control}
          name="channel"
          render={({ field }) => (
            <RadioCardGroup
              label="How would you like to verify?"
              value={field.value}
              onValueChange={field.onChange}
              options={[
                { value: "email_otp", title: "Email me a code", description: "Sent to the email your library has on file." },
                { value: "owner_code", title: "I have a code from my library", description: "The library gave you a code in person." },
              ]}
            />
          )}
        />
        {formError && <Alert tone="danger">{formError}</Alert>}
        <Button type="submit" fullWidth loading={isSubmitting}>
          Continue
        </Button>
      </form>
    </AuthCard>
  );
}

function CompleteStep({ phone, channel, onBack }: { phone: string; channel: ClaimChannel; onBack: () => void }) {
  const { completeClaim } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting, isSubmitSuccessful },
  } = useForm<ClaimCompleteValues>({ resolver: zodResolver(claimCompleteSchema), mode: "onBlur" });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await completeClaim({
        phone,
        code: values.code,
        password: values.password,
        ...(values.email ? { email: values.email } : {}),
        ...(values.name ? { name: values.name } : {}),
      });
    } catch (error) {
      setFormError(applyServerError(error, setError, COMPLETE_FIELDS, { EMAIL_TAKEN: "email" }));
    }
  });

  return (
    <AuthCard
      title="Enter your code"
      description={
        channel === "email_otp"
          ? "If we found a matching membership, we've emailed you a 6-digit code. It is valid for 10 minutes."
          : "Enter the code your library gave you."
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormField label={channel === "email_otp" ? "6-digit code" : "Library code"} required error={errors.code?.message}>
          {channel === "email_otp" ? (
            <OtpField {...register("code")} />
          ) : (
            <Input autoComplete="off" autoCapitalize="characters" maxLength={16} className="font-mono uppercase" {...register("code")} />
          )}
        </FormField>
        <FormField label="Choose a password" required hint={PASSWORD_HINT} error={errors.password?.message}>
          <PasswordInput autoComplete="new-password" {...register("password")} />
        </FormField>
        <FormField
          label="Email"
          hint="Only needed if your library did not have your email. You will use it to log in."
          error={errors.email?.message}
        >
          <Input type="email" autoComplete="email" inputMode="email" {...register("email")} />
        </FormField>
        {formError && <Alert tone="danger">{formError}</Alert>}
        <Button type="submit" fullWidth loading={isSubmitting || isSubmitSuccessful}>
          Link my account
        </Button>
        <Button variant="ghost" fullWidth onClick={onBack}>
          Back
        </Button>
      </form>
    </AuthCard>
  );
}
