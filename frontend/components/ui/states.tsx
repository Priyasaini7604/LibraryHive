import { CircleAlert, Inbox } from "lucide-react";

import { cn } from "@/lib/cn";
import { ApiError, userMessage } from "@/lib/errors";

import { Button } from "./button";

/** Content-shaped loading placeholder (UI_ARCHITECTURE.md 10.1). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-slate-200 motion-reduce:animate-none", className)} />;
}

export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 rounded-xl border border-dashed border-slate-300 p-8 text-center", className)}>
      <span aria-hidden="true" className="text-slate-400">
        {icon ?? <Inbox className="size-8" />}
      </span>
      <p className="font-medium text-slate-900">{title}</p>
      {description && <p className="max-w-md text-sm text-slate-600">{description}</p>}
      {action}
    </div>
  );
}

/** Friendly error with retry and the request reference for support. */
export function ErrorState({
  error,
  onRetry,
  title = "We couldn't load this.",
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  className?: string;
}) {
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-8 text-center", className)}>
      <CircleAlert aria-hidden="true" className="size-8 text-red-600" />
      <p className="font-medium text-red-900">{title}</p>
      <p className="max-w-md text-sm text-red-800">{userMessage(error)}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
      {requestId && <p className="text-xs text-red-700">Reference: {requestId}</p>}
    </div>
  );
}

/** Shown while the session is restored, so protected content never flashes. */
export function FullPageSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 sm:p-8" aria-busy="true">
      <span className="sr-only" role="status">
        Loading
      </span>
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
