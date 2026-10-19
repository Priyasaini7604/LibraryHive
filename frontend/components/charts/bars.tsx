import { ProgressBar } from "@/components/ui/surface";

/** Seats by state as a stacked bar with the numbers written out (never colour alone). */
export function OccupancyBar({ occupied, reserved, empty, disabled = 0, label }: { occupied: number; reserved: number; empty: number; disabled?: number; label: string }) {
  const total = occupied + reserved + empty + disabled;
  const pct = (value: number) => (total === 0 ? 0 : (value / total) * 100);
  return (
    <figure aria-label={label} className="flex flex-col gap-2">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${occupied} taken, ${reserved} reserved, ${empty} free of ${total} seats`}>
        <div className="bg-slate-500" style={{ width: `${pct(occupied)}%` }} />
        <div className="bg-amber-400" style={{ width: `${pct(reserved)}%` }} />
        <div className="bg-emerald-500" style={{ width: `${pct(empty)}%` }} />
      </div>
      <figcaption className="text-sm text-slate-700">
        {occupied} taken · {reserved} reserved · {empty} free{disabled ? ` · ${disabled} under maintenance` : ""} · {total} seats
      </figcaption>
    </figure>
  );
}

/** Members per exam domain as horizontal bars, largest first (DASH-03). */
export function DomainBars({ rows }: { rows: { code: string; name: string; count: number }[] }) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  return (
    <ul aria-label="Members by exam" className="flex flex-col gap-3">
      {rows.map((row) => (
        <li key={row.code} className="flex flex-col gap-1">
          <div className="flex justify-between text-sm text-slate-800">
            <span>{row.name}</span>
            <span className="tabular-nums">{row.count}</span>
          </div>
          <ProgressBar value={row.count} max={max} label={`${row.name}: ${row.count}`} />
        </li>
      ))}
    </ul>
  );
}
