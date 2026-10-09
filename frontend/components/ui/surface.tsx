import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)} {...props} />;
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-4 sm:p-5", className)} {...props} />;
}

export function CardTitle({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cn("text-lg font-semibold text-slate-900", className)} {...props}>
      {children}
    </h2>
  );
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pt-0 sm:p-5 sm:pt-0", className)} {...props} />;
}

export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "brand";

const BADGE_TONES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  info: "bg-sky-50 text-sky-800",
  success: "bg-green-50 text-green-800",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-red-50 text-red-800",
  brand: "bg-blue-50 text-blue-800",
};

export function Badge({ tone = "neutral", className, ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium", BADGE_TONES[tone], className)}
      {...props}
    />
  );
}

/**
 * Status shown with colour + icon + text, never colour alone (UI_ARCHITECTURE.md 1, principle 5).
 * Domain components map their statuses (seat, membership, payment...) onto this.
 */
export function StatusBadge({ tone, icon, label }: { tone: Tone; icon?: React.ReactNode; label: string }) {
  return (
    <Badge tone={tone}>
      {icon && <span aria-hidden="true">{icon}</span>}
      {label}
    </Badge>
  );
}

const ALERT_STYLES = {
  info: { classes: "border-sky-200 bg-sky-50 text-sky-900", Icon: Info },
  success: { classes: "border-green-200 bg-green-50 text-green-900", Icon: CheckCircle2 },
  warning: { classes: "border-amber-200 bg-amber-50 text-amber-900", Icon: TriangleAlert },
  danger: { classes: "border-red-200 bg-red-50 text-red-900", Icon: AlertCircle },
} as const;

export interface AlertProps {
  tone?: keyof typeof ALERT_STYLES;
  title?: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

/** Inline message. Danger alerts are announced immediately (role="alert"). */
export function Alert({ tone = "info", title, children, action, className }: AlertProps) {
  const { classes, Icon } = ALERT_STYLES[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex gap-3 rounded-lg border p-3 text-sm", classes, className)}>
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="flex flex-1 flex-col gap-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (
    <span
      aria-hidden="true"
      className={cn("inline-flex size-9 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-800", className)}
    >
      {initials || "?"}
    </span>
  );
}

export function ProgressBar({ value, max = 100, label }: { value: number; max?: number; label: string }) {
  const percent = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
    >
      <div className="h-full rounded-full bg-blue-600" style={{ width: `${percent}%` }} />
    </div>
  );
}
