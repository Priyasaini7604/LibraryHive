import { forwardRef } from "react";

import { cn } from "@/lib/cn";

const fieldClasses = cn(
  "w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-400",
  "focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30",
  "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500",
  "aria-[invalid=true]:border-red-600 aria-[invalid=true]:focus:ring-red-600/30",
);

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

/** Text input. 16px text prevents iOS zoom on focus (UI_ARCHITECTURE.md 2.1). */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn(fieldClasses, "h-11", className)} {...props} />;
});

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn(fieldClasses, "min-h-28 py-2", className)} {...props} />;
});

/** Indian mobile number input; the server normalises to E.164. */
export const PhoneField = forwardRef<HTMLInputElement, InputProps>(function PhoneField(props, ref) {
  return <Input ref={ref} type="tel" inputMode="tel" autoComplete="tel" placeholder="98765 43210" {...props} />;
});

/** One-time code input (claim OTP, password reset). */
export const OtpField = forwardRef<HTMLInputElement, InputProps>(function OtpField({ className, ...props }, ref) {
  return (
    <Input
      ref={ref}
      inputMode="numeric"
      autoComplete="one-time-code"
      pattern="[0-9]*"
      maxLength={6}
      className={cn("text-center font-mono text-lg tracking-[0.5em]", className)}
      {...props}
    />
  );
});

/** Native date picker; pass min/max from business rules. */
export const DateField = forwardRef<HTMLInputElement, InputProps>(function DateField(props, ref) {
  return <Input ref={ref} type="date" {...props} />;
});
