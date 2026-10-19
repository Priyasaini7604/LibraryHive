import Link from "next/link";

import { cn } from "@/lib/cn";

/**
 * One dashboard number. When `href` is given the whole card links to the list the number was counted from, so
 * the figure and the list it opens always agree (T23). The label is the card's accessible name.
 */
export function StatCard({
  label,
  value,
  hint,
  href,
  tone = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  href?: string;
  tone?: "neutral" | "warning" | "danger" | "success";
}) {
  const body = (
    <>
      <p className="text-sm text-slate-600">{label}</p>
      <p
        className={cn(
          "font-display text-3xl font-bold tabular-nums tracking-tight text-slate-900",
          tone === "danger" && "text-red-700",
          tone === "warning" && "text-amber-700",
          tone === "success" && "text-emerald-700",
        )}
      >
        {value}
      </p>
      {hint && <p className="text-xs text-slate-600">{hint}</p>}
    </>
  );
  const classes = "flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white bg-gradient-to-b from-white/[0.035] to-transparent p-5";
  return href ? (
    <Link href={href} className={cn(classes, "card-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400")}>
      {body}
    </Link>
  ) : (
    <div className={classes}>{body}</div>
  );
}
