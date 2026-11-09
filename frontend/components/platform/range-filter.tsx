"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { DateField } from "@/components/ui/input";
import { addDays, businessDate } from "@/lib/format";
import type { DateRange } from "@/lib/platform-types";

export type Preset = 7 | 30 | 90 | "custom";
export const PRESETS: { value: Preset; label: string }[] = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: "custom", label: "Custom" },
];

export interface RangeState {
  preset: Preset;
  range: DateRange;
}

export function presetRange(days: number): DateRange {
  const today = businessDate();
  return { from: addDays(today, -(days - 1)), to: today };
}

/** Date-range state shared by the dashboard screens; defaults to the last 30 days. */
export function useDateRange(): [RangeState, (next: RangeState) => void] {
  return useState<RangeState>(() => ({ preset: 30, range: presetRange(30) }));
}

/** 7 / 30 / 90 day presets plus a custom from-to range (the backend caps a range at 366 days). */
export function RangeFilter({ value, onChange }: { value: RangeState; onChange: (next: RangeState) => void }) {
  const { preset, range } = value;
  const invalid = range.to < range.from;
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div role="group" aria-label="Date range" className="flex gap-1">
        {PRESETS.map((option) => (
          <Button
            key={String(option.value)}
            size="sm"
            variant={preset === option.value ? "primary" : "secondary"}
            aria-pressed={preset === option.value}
            onClick={() =>
              onChange({
                preset: option.value,
                range: option.value === "custom" ? range : presetRange(option.value),
              })
            }
          >
            {option.label}
          </Button>
        ))}
      </div>
      {preset === "custom" && (
        <div className="flex flex-wrap items-end gap-2">
          <FormField label="From">
            <DateField
              value={range.from}
              max={range.to}
              onChange={(event) => event.target.value && onChange({ preset, range: { ...range, from: event.target.value } })}
            />
          </FormField>
          <FormField label="To">
            <DateField
              value={range.to}
              min={range.from}
              max={businessDate()}
              onChange={(event) => event.target.value && onChange({ preset, range: { ...range, to: event.target.value } })}
            />
          </FormField>
          {invalid && (
            <p role="alert" className="text-sm text-red-700">
              End date must not be before the start date.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
