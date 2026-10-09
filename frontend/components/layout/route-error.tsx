"use client";

import { ErrorState } from "@/components/ui/states";

/** Shared body for route-level error.tsx files. */
export function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-xl py-10">
      <ErrorState error={error} onRetry={reset} title="This page couldn't be shown." />
    </div>
  );
}
