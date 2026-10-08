import { cloneElement, isValidElement, useId } from "react";

import { cn } from "@/lib/cn";

interface FieldControlProps {
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
  "aria-required"?: boolean;
}

export interface FormFieldProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  /** A single form control (Input, Textarea, Select trigger...). */
  children: React.ReactElement<FieldControlProps>;
}

/**
 * Label + control + hint + error with the ARIA wiring done once
 * (UI_ARCHITECTURE.md 7 and 11): the error is linked with aria-describedby.
 */
export function FormField({ label, hint, error, required, className, children }: FormFieldProps) {
  const autoId = useId();
  const controlId = children.props.id ?? `field-${autoId}`;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  const control = isValidElement(children)
    ? cloneElement(children, {
        id: controlId,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
        "aria-required": required || undefined,
      })
    : children;

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={controlId} className="text-sm font-medium text-slate-900">
        {label}
        {required && (
          <span className="text-red-600">
            {" "}
            *<span className="sr-only"> (required)</span>
          </span>
        )}
      </label>
      {control}
      {hint && (
        <p id={hintId} className="text-sm text-slate-600">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
