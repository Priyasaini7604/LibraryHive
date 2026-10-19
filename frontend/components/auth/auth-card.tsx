import { Card, CardContent } from "@/components/ui/surface";
import { Skeleton } from "@/components/ui/states";

/** Centered card used by every auth screen (UI_ARCHITECTURE.md 6). */
export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-md px-4 py-8 sm:py-12">
      <Card>
        <CardContent className="flex flex-col gap-6 p-6 sm:p-8">
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-extrabold tracking-[-0.025em] text-slate-900">{title}</h1>
            {description && <p className="text-sm text-slate-600">{description}</p>}
          </div>
          {children}
        </CardContent>
      </Card>
      {footer && <div className="mt-4 text-center text-sm text-slate-600">{footer}</div>}
    </div>
  );
}

/** Suspense fallback while the query string is read. */
export function AuthCardSkeleton() {
  return (
    <div className="mx-auto w-full max-w-md px-4 py-8 sm:py-12" aria-busy="true">
      <span className="sr-only" role="status">
        Loading
      </span>
      <Card>
        <CardContent className="flex flex-col gap-4 p-6 sm:p-8">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}
