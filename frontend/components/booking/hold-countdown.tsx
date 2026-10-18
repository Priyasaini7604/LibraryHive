"use client";

import { Timer } from "lucide-react";
import { useEffect, useState } from "react";

import { serverNow } from "@/lib/api-client";
import { cn } from "@/lib/cn";

function format(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/**
 * Time left on a seat hold, from the server clock so a wrong device clock cannot break it (UI_ARCHITECTURE.md
 * 5.3). Screen readers hear it only at 5 minutes and 1 minute. Reaching zero decides nothing by itself: the
 * parent re-reads the hold and the server's answer wins.
 */
export function HoldCountdown({
  expiresAt,
  paused = false,
  onElapsed,
}: {
  expiresAt: string;
  paused?: boolean;
  onElapsed: () => void;
}) {
  const end = Date.parse(expiresAt);
  const [left, setLeft] = useState(() => end - serverNow());

  useEffect(() => {
    if (paused) return;
    const tick = () => setLeft(end - serverNow());
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [end, paused]);

  useEffect(() => {
    if (!paused && left <= 0) onElapsed();
  }, [left, paused, onElapsed]);

  const announce = left <= 60_000 ? "Less than 1 minute left on your seat hold." : left <= 300_000 ? "Less than 5 minutes left on your seat hold." : "";

  return (
    <p
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium",
        left <= 60_000 ? "border-red-300 bg-red-50 text-red-800" : left <= 120_000 ? "border-amber-300 bg-amber-50 text-amber-900" : "border-slate-300 bg-white text-slate-800",
      )}
    >
      <Timer aria-hidden="true" className="size-4" />
      <span>
        Seat held for <span className="tabular-nums">{format(left)}</span>
      </span>
      <span className="sr-only" role="status" aria-live="polite">
        {announce}
      </span>
    </p>
  );
}
