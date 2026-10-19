"use client";

import { Ban, Clock, User } from "lucide-react";
import { useMemo, useRef } from "react";

import { cn } from "@/lib/cn";
import type { SeatStatus } from "@/lib/types";

export interface MapSeat {
  id: string;
  label: string;
  row_label: string;
  position: number | null;
  status: SeatStatus | null;
}

export const STATUS_TEXT: Record<SeatStatus, string> = {
  empty: "free",
  reserved: "reserved",
  occupied: "taken",
  disabled: "under maintenance",
};

const STYLES: Record<SeatStatus, string> = {
  empty: "border-emerald-600 bg-white text-slate-900 hover:bg-emerald-50",
  reserved: "border-amber-500 bg-amber-50 text-amber-900",
  occupied: "border-slate-400 bg-slate-200 text-slate-700",
  disabled: "border-dashed border-slate-400 bg-slate-50 text-slate-500",
};

function StatusIcon({ status }: { status: SeatStatus }) {
  if (status === "reserved") return <Clock aria-hidden="true" className="size-3.5" />;
  if (status === "occupied") return <User aria-hidden="true" className="size-3.5" />;
  if (status === "disabled") return <Ban aria-hidden="true" className="size-3.5" />;
  return null;
}

function byLayout(a: MapSeat, b: MapSeat): number {
  if (a.row_label !== b.row_label) return a.row_label.localeCompare(b.row_label, undefined, { numeric: true });
  const left = a.position ?? Number.MAX_SAFE_INTEGER;
  const right = b.position ?? Number.MAX_SAFE_INTEGER;
  return left !== right ? left - right : a.label.localeCompare(b.label, undefined, { numeric: true });
}

export interface SeatMapProps {
  seats: MapSeat[];
  selectedId?: string | null;
  onSelect?: (seat: MapSeat) => void;
  /** Which seats can be chosen. Students: free seats only. Owners: every seat (to open its side panel). */
  isSelectable?: (seat: MapSeat) => boolean;
  /** Describes the map to assistive technology. */
  label: string;
}

/**
 * The seat grid (UI_ARCHITECTURE.md 5.2). Each row is a labelled group of buttons; arrow keys move between
 * seats. A seat's state is always in its accessible name and shown with an icon, never by colour alone.
 */
export function SeatMap({ seats, selectedId, onSelect, isSelectable = (seat) => seat.status === "empty", label }: SeatMapProps) {
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const rows = useMemo(() => {
    const grouped = new Map<string, MapSeat[]>();
    for (const seat of [...seats].sort(byLayout)) {
      grouped.set(seat.row_label, [...(grouped.get(seat.row_label) ?? []), seat]);
    }
    return [...grouped.entries()];
  }, [seats]);
  const order = useMemo(() => rows.flatMap(([, rowSeats]) => rowSeats.map((seat) => seat.id)), [rows]);

  function focusSeat(id: string | undefined) {
    if (id) refs.current.get(id)?.focus();
  }

  function move(from: string, step: number) {
    const index = order.indexOf(from);
    focusSeat(order[Math.min(order.length - 1, Math.max(0, index + step))]);
  }

  /** Up and down keep the column: the seat at the same place in the neighbouring row (or its last seat). */
  function vertical(seat: MapSeat, rowSeats: MapSeat[], delta: number) {
    const rowIndex = rows.findIndex(([, list]) => list === rowSeats);
    const neighbour = rows[rowIndex + delta]?.[1];
    if (!neighbour || neighbour.length === 0) return;
    focusSeat(neighbour[Math.min(rowSeats.indexOf(seat), neighbour.length - 1)]?.id);
  }

  function onKeyDown(event: React.KeyboardEvent, seat: MapSeat, rowSeats: MapSeat[]) {
    const keys: Record<string, () => void> = {
      ArrowRight: () => move(seat.id, 1),
      ArrowLeft: () => move(seat.id, -1),
      ArrowDown: () => vertical(seat, rowSeats, 1),
      ArrowUp: () => vertical(seat, rowSeats, -1),
      Home: () => focusSeat(order[0]),
      End: () => focusSeat(order[order.length - 1]),
    };
    const handler = keys[event.key];
    if (handler) {
      event.preventDefault();
      handler();
    }
  }

  if (seats.length === 0) return null;
  const firstFocusable = selectedId && order.includes(selectedId) ? selectedId : order[0];

  return (
    <div role="group" aria-label={label} className="flex flex-col gap-3 overflow-x-auto pb-1">
      {rows.map(([rowLabel, rowSeats]) => (
        <div key={rowLabel || "unlabelled"} role="group" aria-label={rowLabel ? `Row ${rowLabel}` : "Seats"} className="flex items-center gap-2">
          {rowLabel && (
            <span aria-hidden="true" className="w-6 shrink-0 text-center text-xs font-medium text-slate-500">
              {rowLabel}
            </span>
          )}
          <div className="flex flex-wrap gap-2">
            {rowSeats.map((seat) => {
              const status: SeatStatus = seat.status ?? "disabled";
              const selectable = Boolean(onSelect) && isSelectable(seat);
              const selected = seat.id === selectedId;
              return (
                <button
                  key={seat.id}
                  type="button"
                  ref={(node) => {
                    if (node) refs.current.set(seat.id, node);
                    else refs.current.delete(seat.id);
                  }}
                  tabIndex={seat.id === firstFocusable ? 0 : -1}
                  aria-label={`Seat ${seat.label}, ${STATUS_TEXT[status]}`}
                  aria-pressed={selectable ? selected : undefined}
                  aria-disabled={!selectable || undefined}
                  onClick={() => selectable && onSelect?.(seat)}
                  onKeyDown={(event) => onKeyDown(event, seat, rowSeats)}
                  className={cn(
                    "flex size-12 flex-col items-center justify-center gap-0.5 rounded-lg border-2 text-xs font-medium",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2",
                    STYLES[status],
                    !selectable && "cursor-not-allowed",
                    selected && "ring-2 ring-blue-600 ring-offset-2",
                  )}
                >
                  <span>{seat.label}</span>
                  <StatusIcon status={status} />
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/** What each seat style means; icons repeat the meaning for people who do not see colour. */
export function SeatLegend({ className }: { className?: string }) {
  const items: { status: SeatStatus; label: string }[] = [
    { status: "empty", label: "Free" },
    { status: "reserved", label: "Reserved" },
    { status: "occupied", label: "Taken" },
    { status: "disabled", label: "Under maintenance" },
  ];
  return (
    <ul aria-label="Seat legend" className={cn("flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-700", className)}>
      {items.map((item) => (
        <li key={item.status} className="flex items-center gap-1.5">
          <span aria-hidden="true" className={cn("flex size-5 items-center justify-center rounded border-2", STYLES[item.status])}>
            <StatusIcon status={item.status} />
          </span>
          {item.label}
        </li>
      ))}
    </ul>
  );
}
