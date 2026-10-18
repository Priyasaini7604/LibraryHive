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
          "text-2xl font-semibold tabular-nums text-slate-900",
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
  const classes = "flex flex-col gap-0.5 rounded-xl border border-slate-200 bg-white p-4";
  return href ? (
    <Link href={href} className={cn(classes, "hover:border-blue-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600")}>
      {body}
    </Link>
  ) : (
    <div className={classes}>{body}</div>
  );
}
