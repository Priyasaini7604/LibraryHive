import React from "react";
import { LayoutGrid } from "lucide-react";
import { SeatSummary } from "@/lib/types";

interface SeatMapSectionProps {
  seatSummary?: SeatSummary;
}

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "22px",
  boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
};

/**
 * Placeholder area for the live seat map. It only shows the counts already
 * returned with the library; the seat grid itself is not built yet.
 */
export default function SeatMapSection({ seatSummary }: SeatMapSectionProps) {
  const hasSeatData =
    !!seatSummary &&
    seatSummary.empty + seatSummary.reserved + seatSummary.occupied > 0;

  const tiles = hasSeatData
    ? [
        { label: "Available", value: seatSummary.empty, color: "#166534", bg: "#dcfce7" },
        { label: "Reserved", value: seatSummary.reserved, color: "#92400e", bg: "#fef3c7" },
        { label: "Occupied", value: seatSummary.occupied, color: "#991b1b", bg: "#fee2e2" },
        { label: "Total", value: seatSummary.total, color: "#0f172a", bg: "#f1f5f9" },
      ]
    : [];

  return (
    <section id="seat-map" style={cardStyle}>
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

      {hasSeatData ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
            gap: "12px",
            marginTop: "16px",
          }}
        >
          {tiles.map((tile) => (
            <div
              key={tile.label}
              style={{
                background: tile.bg,
                borderRadius: "10px",
                padding: "12px 14px",
              }}
            >
              <div style={{ fontSize: "22px", fontWeight: 800, color: tile.color }}>
                {tile.value}
              </div>
              <div style={{ fontSize: "12px", fontWeight: 600, color: tile.color }}>
                {tile.label}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: "14px", color: "#94a3b8", marginTop: "16px" }}>
          This library has not published its seats yet.
        </div>
      )}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
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
        The live seat map will appear here.
      </div>
    </section>
  );
}
