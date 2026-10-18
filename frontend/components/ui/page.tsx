import { cn } from "@/lib/cn";

import { Skeleton } from "./states";

/** Title row of a screen: heading, optional description and the primary actions on the right. */
export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {description && <p className="max-w-2xl text-sm text-slate-600">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

/** A screen body: consistent width and spacing for every owner and student page. */
export function Page({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6", className)}>{children}</div>;
}

/** Content-shaped loading state for lists; announced once to screen readers. */
export function LoadingList({ label, rows = 3 }: { label: string; rows?: number }) {
  return (
    <div aria-busy="true" className="flex flex-col gap-3">
      <span className="sr-only" role="status">
        {label}
      </span>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-20 w-full" />
      ))}
    </div>
  );
}

/** A label and its value, stacked; used for facts on cards and detail pages. */
export function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-slate-600">{label}</dt>
      <dd className="text-sm font-medium text-slate-900">{children}</dd>
    </div>
  );
}
