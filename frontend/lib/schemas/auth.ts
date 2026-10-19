/**
 * zod schemas for the auth and profile forms (UI_ARCHITECTURE.md 6 and 7). They mirror the
 * backend rules in BACKEND_ARCHITECTURE.md as a convenience only; the server always revalidates.
 * Field names match the API payloads so server `details` map straight onto fields.
 */

import { z } from "zod";

/** Indian mobile number, typed freely: "98765 43210", "+91-98765-43210", "09876543210". */
const INDIAN_MOBILE = /^(?:\+?91|0)?[6-9]\d{9}$/;

export const phoneSchema = z
  .string()
  .trim()
  .min(1, "Enter your phone number.")
  .refine((value) => INDIAN_MOBILE.test(value.replace(/[\s-]/g, "")), "Enter a valid Indian mobile number.");

export const emailSchema = z.string().trim().min(1, "Enter your email address.").pipe(z.email("Enter a valid email address."));

/** Only the rules the client can check; similarity and common-password checks stay on the server. */
export const PASSWORD_HINT = "At least 8 characters. Avoid common passwords and passwords that are only numbers.";
export const passwordSchema = z
  .string()
  .min(8, "Use at least 8 characters.")
  .max(128, "Use at most 128 characters.")
  .refine((value) => !/^\d+$/.test(value), "Use more than just numbers.");

export const nameSchema = z.string().trim().min(2, "Enter your name (at least 2 characters).").max(150, "Use at most 150 characters.");

const sixDigitCode = z.string().trim().regex(/^\d{6}$/, "Enter the 6-digit code from your email.");

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password."),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  role: z.enum(["student", "owner"]),
  name: nameSchema,
  email: emailSchema,
  phone: phoneSchema,
  password: passwordSchema,
  domain_code: z.string().optional(),
});
export type RegisterValues = z.infer<typeof registerSchema>;

export const claimStartSchema = z.object({
  phone: phoneSchema,
  channel: z.enum(["email_otp", "owner_code"]),
});
export type ClaimStartValues = z.infer<typeof claimStartSchema>;

/** Email codes are 6 digits; owner codes are 8 letters and digits (hyphens and spaces are ignored by the server). */
const claimCode = z
  .string()
  .trim()
  .min(1, "Enter your code.")
  .refine((value) => /^[A-Za-z0-9\s-]{6,16}$/.test(value), "Enter the code exactly as you received it.");

export const claimCompleteSchema = z.object({
  code: claimCode,
  password: passwordSchema,
  email: z.union([emailSchema, z.literal("")]).optional(),
  name: z.union([nameSchema, z.literal("")]).optional(),
});
export type ClaimCompleteValues = z.infer<typeof claimCompleteSchema>;

export const forgotPasswordSchema = z.object({ email: emailSchema });
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    email: emailSchema,
    code: sixDigitCode,
    new_password: passwordSchema,
    confirm_password: z.string().min(1, "Repeat your new password."),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "The passwords do not match.",
  });
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

export const profileSchema = z.object({
  name: nameSchema,
  phone: phoneSchema,
  domain_code: z.string().optional(),
});
export type ProfileValues = z.infer<typeof profileSchema>;
