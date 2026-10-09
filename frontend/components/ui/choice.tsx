"use client";

import { Check, ChevronDown } from "lucide-react";
import { Checkbox as CheckboxPrimitive, RadioGroup, Select as SelectPrimitive } from "radix-ui";
import { forwardRef } from "react";

import { cn } from "@/lib/cn";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  id?: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  name?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
  "aria-required"?: boolean;
}

/** Accessible select (Radix); works inside FormField. */
export const Select = forwardRef<HTMLButtonElement, SelectProps>(function Select(
  { id, value, defaultValue, onValueChange, options, placeholder = "Select…", disabled, name, ...aria },
  ref,
) {
  return (
    <SelectPrimitive.Root value={value} defaultValue={defaultValue} onValueChange={onValueChange} disabled={disabled} name={name}>
      <SelectPrimitive.Trigger
        ref={ref}
        id={id}
        {...aria}
        className={cn(
          "flex h-11 w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 text-left text-base",
          "focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30 disabled:bg-slate-50",
          "aria-[invalid=true]:border-red-600 data-[placeholder]:text-slate-400",
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon>
          <ChevronDown aria-hidden="true" className="size-4 text-slate-500" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          className="z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg"
        >
          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                disabled={option.disabled}
                className="relative flex h-10 cursor-pointer select-none items-center rounded-md pl-8 pr-3 text-sm text-slate-900 outline-none data-[disabled]:cursor-not-allowed data-[highlighted]:bg-blue-50 data-[disabled]:text-slate-400"
              >
                <SelectPrimitive.ItemIndicator className="absolute left-2">
                  <Check aria-hidden="true" className="size-4 text-blue-600" />
                </SelectPrimitive.ItemIndicator>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
});

export interface CheckboxProps {
  id?: string;
  label: string;
  checked?: boolean;
  defaultChecked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  name?: string;
}

export function Checkbox({ id, label, onCheckedChange, ...props }: CheckboxProps) {
  return (
    <label className="inline-flex min-h-11 cursor-pointer items-center gap-3 text-sm text-slate-900">
      <CheckboxPrimitive.Root
        id={id}
        onCheckedChange={(state) => onCheckedChange?.(state === true)}
        className="flex size-5 shrink-0 items-center justify-center rounded border border-slate-400 bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 data-[state=checked]:border-blue-600 data-[state=checked]:bg-blue-600"
        {...props}
      >
        <CheckboxPrimitive.Indicator>
          <Check aria-hidden="true" className="size-3.5 text-white" />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {label}
    </label>
  );
}

export interface RadioCardOption {
  value: string;
  title: string;
  description?: string;
  disabled?: boolean;
}

export interface RadioCardGroupProps {
  label: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  options: RadioCardOption[];
  className?: string;
}

/** Large tappable radio options, e.g. plan selection. */
export function RadioCardGroup({ label, options, className, ...props }: RadioCardGroupProps) {
  return (
    <RadioGroup.Root aria-label={label} className={cn("grid gap-3", className)} {...props}>
      {options.map((option) => (
        <RadioGroup.Item
          key={option.value}
          value={option.value}
          disabled={option.disabled}
          className={cn(
            "flex w-full items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-left",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2",
            "data-[state=checked]:border-blue-600 data-[state=checked]:bg-blue-50 data-[disabled]:opacity-50",
          )}
        >
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border border-slate-400">
            <RadioGroup.Indicator className="size-2.5 rounded-full bg-blue-600" />
          </span>
          <span className="flex flex-col">
            <span className="font-medium text-slate-900">{option.title}</span>
            {option.description && <span className="text-sm text-slate-600">{option.description}</span>}
          </span>
        </RadioGroup.Item>
      ))}
    </RadioGroup.Root>
  );
}
