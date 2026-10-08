import { Slot } from "radix-ui";
import { forwardRef } from "react";

import { cn } from "@/lib/cn";

import { Spinner } from "./spinner";

const VARIANTS = {
  primary: "bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300",
  secondary: "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50 disabled:text-slate-400",
  ghost: "text-slate-700 hover:bg-slate-100 disabled:text-slate-400",
  danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300",
} as const;

const SIZES = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4 text-sm", // 44px: minimum touch target (UI_ARCHITECTURE.md 8)
  lg: "h-12 px-5 text-base",
} as const;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  loading?: boolean;
  fullWidth?: boolean;
  /** Render the child element (e.g. a Link) with button styling. */
  asChild?: boolean;
}

export const buttonClasses = (
  variant: keyof typeof VARIANTS = "primary",
  size: keyof typeof SIZES = "md",
  fullWidth = false,
) =>
  cn(
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-150",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed motion-reduce:transition-none",
    VARIANTS[variant],
    SIZES[size],
    fullWidth && "w-full",
  );

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, fullWidth = false, asChild = false, className, children,
    disabled, type, ...props },
  ref,
) {
  if (asChild) {
    return (
      <Slot.Root className={cn(buttonClasses(variant, size, fullWidth), className)} {...props}>
        {children}
      </Slot.Root>
    );
  }
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      className={cn(buttonClasses(variant, size, fullWidth), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Spinner label="Working" />}
      {children}
    </button>
  );
});

export interface IconButtonProps extends Omit<ButtonProps, "children" | "asChild"> {
  /** Accessible name; icon-only buttons must have one. */
  label: string;
  icon: React.ReactNode;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, variant = "ghost", size = "md", className, ...props },
  ref,
) {
  return (
    <Button ref={ref} variant={variant} size={size} aria-label={label} className={cn("aspect-square px-0", className)} {...props}>
      <span aria-hidden="true">{icon}</span>
    </Button>
  );
});
