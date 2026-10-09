"use client";

import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { Tabs as TabsPrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

import { Button } from "./button";

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

export function TabsList({ label, items }: { label: string; items: { value: string; label: string; count?: number }[] }) {
  return (
    <TabsPrimitive.List aria-label={label} className="flex gap-1 overflow-x-auto border-b border-slate-200">
      {items.map((item) => (
        <TabsPrimitive.Trigger
          key={item.value}
          value={item.value}
          className={cn(
            "inline-flex h-11 items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-3 text-sm font-medium text-slate-600",
            "hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600",
            "data-[state=active]:border-blue-600 data-[state=active]:text-blue-700",
          )}
        >
          {item.label}
          {item.count !== undefined && (
            <span className="rounded-full bg-slate-100 px-2 text-xs text-slate-700">{item.count}</span>
          )}
        </TabsPrimitive.Trigger>
      ))}
    </TabsPrimitive.List>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 pt-4">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        <ChevronLeft aria-hidden="true" className="size-4" /> Previous
      </Button>
      <p className="text-sm text-slate-600" aria-live="polite">
        Page {page} of {pages}
      </p>
      <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
        Next <ChevronRight aria-hidden="true" className="size-4" />
      </Button>
    </nav>
  );
}

export interface Step {
  id: string;
  label: string;
  complete: boolean;
}

/** Wizard progress: vertical list on desktop, compact "Step x of y" on phones. */
export function Stepper({ steps, currentId }: { steps: Step[]; currentId: string }) {
  const currentIndex = Math.max(0, steps.findIndex((step) => step.id === currentId));
  return (
    <nav aria-label="Progress">
      <p className="text-sm font-medium text-slate-700 lg:hidden">
        Step {currentIndex + 1} of {steps.length}: {steps[currentIndex]?.label}
      </p>
      <ol className="hidden flex-col gap-1 lg:flex">
        {steps.map((step, index) => {
          const current = step.id === currentId;
          return (
            <li
              key={step.id}
              aria-current={current ? "step" : undefined}
              className={cn("flex items-center gap-3 rounded-lg px-3 py-2 text-sm", current && "bg-blue-50 font-medium text-blue-800")}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs",
                  step.complete ? "border-green-600 bg-green-600 text-white" : "border-slate-300 text-slate-600",
                )}
              >
                {step.complete ? <Check aria-hidden="true" className="size-3.5" /> : index + 1}
              </span>
              {step.label}
              {step.complete && <span className="sr-only">(complete)</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1 text-sm text-slate-600">
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="flex items-center gap-1">
            {index > 0 && <ChevronRight aria-hidden="true" className="size-4 text-slate-400" />}
            {item.href ? (
              <Link href={item.href} className="hover:text-slate-900 hover:underline">
                {item.label}
              </Link>
            ) : (
              <span aria-current="page" className="font-medium text-slate-900">
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
