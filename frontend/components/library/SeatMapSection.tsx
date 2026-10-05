import React, { useEffect, useState } from "react";
import { AlertCircle, Loader2, LayoutGrid, RefreshCw } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { Seat, SeatStatus } from "@/lib/types";

interface SeatMapSectionProps {
  libraryId: string;
}

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "22px",
  boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
};

// Backend status values (seats.models.Seat.STATUS_CHOICES) -> display style.
// Empty = light fill, Reserved = dashed amber, Occupied = solid dark fill,
// so the three states differ by more than hue alone.
const STATUS_STYLES: Record<
  SeatStatus,
  { label: string; bg: string; border: string; color: string; borderStyle: string }
> = {
  empty: {
    label: "Available",
    bg: "#dcfce7",
    border: "#16a34a",
    color: "#166534",
    borderStyle: "solid",
  },
  reserved: {
    label: "Reserved",
    bg: "#fef3c7",
    border: "#d97706",
    color: "#92400e",
    borderStyle: "dashed",
  },
  occupied: {
    label: "Occupied",
    bg: "#b91c1c",
    border: "#b91c1c",
    color: "#ffffff",
    borderStyle: "solid",
  },
};

// Fallback for any status string the backend might return outside the enum.
const UNKNOWN_STYLE = {
  label: "Unknown",
  bg: "#e2e8f0",
  border: "#94a3b8",
  color: "#475569",
  borderStyle: "solid",
};

const getStyle = (status: string) =>
  STATUS_STYLES[status as SeatStatus] || UNKNOWN_STYLE;

const naturalCompare = (a: string, b: string) =>
  a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });

// The API has no row/column fields. Owner setup generates labels like
// "Row A - Seat 3", so when a label follows that pattern we group by the row
// named in the label. Anything else is shown as-is in "Other seats".
const ROW_LABEL = /^\s*row\s+(.+?)\s*[-\u2013]\s*seat\s+(.+?)\s*$/i;

interface SeatGroup {
  title: string | null;
  wide: boolean; // full-label tiles (labels that are not "Row X - Seat N")
  seats: Array<{ seat: Seat; short: string }>;
}

const buildGroups = (seats: Seat[]): SeatGroup[] => {
  const rows = new Map<string, SeatGroup>();
  const other: SeatGroup = { title: "Other seats", wide: true, seats: [] };

  for (const seat of seats) {
    const match = seat.label.match(ROW_LABEL);
    if (match) {
      const rowName = match[1];
      if (!rows.has(rowName)) {
        rows.set(rowName, { title: `Row ${rowName}`, wide: false, seats: [] });
      }
      rows.get(rowName)!.seats.push({ seat, short: match[2] });
    } else {
      other.seats.push({ seat, short: seat.label });
    }
  }

  const groups = Array.from(rows.entries())
    .sort((a, b) => naturalCompare(a[0], b[0]))
    .map(([, group]) => group);

  for (const group of groups) {
    group.seats.sort((a, b) => naturalCompare(a.seat.label, b.seat.label));
  }
  other.seats.sort((a, b) => naturalCompare(a.seat.label, b.seat.label));

  if (other.seats.length > 0) {
    // With no row-style labels at all, a lone "Other seats" heading is noise.
    if (groups.length === 0) other.title = null;
    groups.push(other);
  }
  return groups;
};

function SeatTile({ seat, short, wide }: { seat: Seat; short: string; wide: boolean }) {
  const style = getStyle(seat.status);
  return (
    <div
      title={`${seat.label} - ${style.label}`}
      aria-label={`${seat.label}, ${style.label}`}
      style={{
        boxSizing: "border-box",
        width: wide ? "auto" : "44px",
        minWidth: wide ? "88px" : "44px",
        height: "44px",
        padding: wide ? "0 10px" : 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: style.bg,
        color: style.color,
        border: `2px ${style.borderStyle} ${style.border}`,
        borderRadius: "8px",
        fontSize: "13px",
        fontWeight: 700,
      }}
    >
      {short}
    </div>
  );
}

/**
 * Live seat map. Shows every seat returned by GET /libraries/{id}/seats/ with
 * its current status. View only: no booking and no status changes here.
 */
export default function SeatMapSection({ libraryId }: SeatMapSectionProps) {
  const [seats, setSeats] = useState<Seat[]>([]);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setIsFetching(true);
      setError("");
      try {
        const data = await apiClient.getLibrarySeats(libraryId);
        if (!cancelled) {
          setSeats(Array.isArray(data) ? data : []);
          setHasLoaded(true);
        }
      } catch (err: any) {
        if (!cancelled) {
          const message = err?.message;
          setError(
            message && message !== "null"
              ? message
              : "Failed to load the seat map."
          );
        }
      } finally {
        if (!cancelled) setIsFetching(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [libraryId, reloadKey]);

  // Counts come from the same seats that are drawn, so legend and grid agree.
  const counts = { empty: 0, reserved: 0, occupied: 0, unknown: 0 };
  for (const seat of seats) {
    if (seat.status === "empty") counts.empty++;
    else if (seat.status === "reserved") counts.reserved++;
    else if (seat.status === "occupied") counts.occupied++;
    else counts.unknown++;
  }

  const groups = buildGroups(seats);

  const legendItems: Array<{ key: string; status: string; count: number }> = [
    { key: "empty", status: "empty", count: counts.empty },
    { key: "reserved", status: "reserved", count: counts.reserved },
    { key: "occupied", status: "occupied", count: counts.occupied },
  ];
  if (counts.unknown > 0) {
    legendItems.push({ key: "unknown", status: "unknown", count: counts.unknown });
  }

  let body: React.ReactNode;

  if (!hasLoaded && isFetching) {
    body = (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "10px",
          padding: "40px 0",
          color: "#64748b",
          fontSize: "14px",
        }}
      >
        <Loader2 size={18} />
        Loading seat map...
      </div>
    );
  } else if (!hasLoaded && error) {
    body = (
      <div
        role="alert"
        style={{
          marginTop: "16px",
          background: "#fee2e2",
          border: "1px solid #fecaca",
          color: "#991b1b",
          borderRadius: "10px",
          padding: "16px",
          display: "flex",
          alignItems: "flex-start",
          gap: "10px",
          fontSize: "14px",
        }}
      >
        <AlertCircle size={18} style={{ flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700 }}>Could not load the seat map</div>
          <div style={{ marginTop: "4px" }}>{error}</div>
          <button
            type="button"
            onClick={() => setReloadKey((k) => k + 1)}
            style={{
              marginTop: "12px",
              background: "#991b1b",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              padding: "7px 14px",
              fontSize: "13px",
              fontWeight: 600,
            }}
          >
            Try again
          </button>
        </div>
      </div>
    );
  } else if (seats.length === 0) {
    body = (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "8px",
          marginTop: "16px",
          padding: "36px 16px",
          border: "2px dashed #cbd5e1",
          borderRadius: "10px",
          background: "#f8fafc",
          color: "#64748b",
          textAlign: "center",
          fontSize: "14px",
        }}
      >
        <LayoutGrid size={28} color="#94a3b8" />
        This library has not published its seats yet.
      </div>
    );
  } else {
    body = (
      <>
        {/* Legend */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "10px 18px",
            marginTop: "16px",
          }}
        >
          {legendItems.map((item) => {
            const style = getStyle(item.status);
            return (
              <div
                key={item.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  fontSize: "13px",
                  color: "#334155",
                }}
              >
                <span
                  style={{
                    width: "18px",
                    height: "18px",
                    boxSizing: "border-box",
                    borderRadius: "5px",
                    background: style.bg,
                    border: `2px ${style.borderStyle} ${style.border}`,
                  }}
                />
                <span>
                  {style.label} <strong>({item.count})</strong>
                </span>
              </div>
            );
          })}
        </div>

        {/* Seat groups */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "18px",
            marginTop: "20px",
            opacity: isFetching ? 0.6 : 1,
          }}
        >
          {groups.map((group, index) => (
            <div key={group.title || `group-${index}`}>
              {group.title && (
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "#475569",
                    marginBottom: "8px",
                  }}
                >
                  {group.title}
                </div>
              )}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {group.seats.map(({ seat, short }) => (
                  <SeatTile
                    key={seat.id}
                    seat={seat}
                    short={short}
                    wide={group.wide}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        <p style={{ fontSize: "12px", color: "#94a3b8", marginTop: "18px", marginBottom: 0 }}>
          Seats are grouped by their labels. This is not a physical floor plan.
        </p>
      </>
    );
  }

  return (
    <section id="seat-map" style={cardStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "10px",
          flexWrap: "wrap",
        }}
      >
        <h2
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: "#64748b",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            margin: 0,
          }}
        >
          Seat map
        </h2>

        {hasLoaded && (
          <button
            type="button"
            onClick={() => setReloadKey((k) => k + 1)}
            disabled={isFetching}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              borderRadius: "8px",
              padding: "6px 12px",
              fontSize: "13px",
              fontWeight: 600,
              color: "#2563eb",
              cursor: isFetching ? "not-allowed" : "pointer",
            }}
          >
            <RefreshCw size={14} />
            {isFetching ? "Refreshing..." : "Refresh"}
          </button>
        )}
      </div>

      {/* A refresh that fails keeps the last good map visible. */}
      {hasLoaded && error && (
        <div
          role="alert"
          style={{
            marginTop: "12px",
            fontSize: "13px",
            color: "#991b1b",
            background: "#fee2e2",
            border: "1px solid #fecaca",
            borderRadius: "8px",
            padding: "8px 12px",
          }}
        >
          Could not refresh: {error}
        </div>
      )}

      {body}
    </section>
  );
}
