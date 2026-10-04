import React from "react";
import Link from "next/link";
import { MapPin, Armchair, Navigation, Tag } from "lucide-react";
import { Library, PricingPlan } from "@/lib/types";

interface LibraryCardProps {
  library: Library;
}

const formatPrice = (price: number | string) =>
  Number(price).toLocaleString("en-IN");

/** Cheapest plan by price, ignoring plans with an invalid price. */
const getStartingPlan = (plans?: PricingPlan[]): PricingPlan | null => {
  const valid = (plans || []).filter((p) => !Number.isNaN(Number(p.price)));
  if (!valid.length) return null;
  return valid.reduce((min, p) =>
    Number(p.price) < Number(min.price) ? p : min
  );
};

const formatDuration = (days: number) =>
  days === 30 ? "month" : days === 365 ? "year" : `${days} days`;

export default function LibraryCard({ library }: LibraryCardProps) {
  const summary = library.seat_summary;
  const startingPlan = getStartingPlan(library.plans);

  // The API falls back to total_seats when no seats exist yet, so a library
  // with zero seat records has nothing meaningful to show as availability.
  const hasSeatData =
    !!summary && summary.empty + summary.reserved + summary.occupied > 0;

  let availabilityColors = { bg: "#dcfce7", fg: "#166534" };
  if (hasSeatData) {
    if (summary.empty === 0) {
      availabilityColors = { bg: "#fee2e2", fg: "#991b1b" };
    } else if (summary.empty / summary.total <= 0.2) {
      availabilityColors = { bg: "#fef3c7", fg: "#92400e" };
    }
  }

  const unavailableCount = hasSeatData ? summary.total - summary.empty : 0;
  const filledPercent = hasSeatData
    ? Math.round((unavailableCount / summary.total) * 100)
    : 0;

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        borderRadius: "12px",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "14px",
        boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
      }}
    >
      {/* Name, address, distance */}
      <div>
        <h2
          style={{
            fontSize: "18px",
            fontWeight: 700,
            color: "#0f172a",
            margin: 0,
          }}
        >
          {library.name}
        </h2>

        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "6px",
            marginTop: "6px",
            fontSize: "13px",
            color: "#64748b",
          }}
        >
          <MapPin size={15} style={{ flexShrink: 0, marginTop: "2px" }} />
          <span>{library.address}</span>
        </div>

        {typeof library.distance_km === "number" && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              marginTop: "8px",
              fontSize: "13px",
              fontWeight: 600,
              color: "#2563eb",
            }}
          >
            <Navigation size={14} />
            {library.distance_km} km away
          </div>
        )}
      </div>

      {/* Seat availability */}
      <div
        style={{
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "12px 14px",
        }}
      >
        {hasSeatData ? (
          <>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "8px",
                flexWrap: "wrap",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "7px",
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#0f172a",
                }}
              >
                <Armchair size={17} color="#475569" />
                {summary.empty} / {summary.total} seats available
              </div>
              <span
                style={{
                  background: availabilityColors.bg,
                  color: availabilityColors.fg,
                  borderRadius: "999px",
                  padding: "2px 10px",
                  fontSize: "12px",
                  fontWeight: 700,
                }}
              >
                {summary.empty === 0 ? "Full" : `${summary.empty} free`}
              </span>
            </div>

            <div
              style={{
                height: "6px",
                background: "#e2e8f0",
                borderRadius: "999px",
                overflow: "hidden",
                marginTop: "10px",
              }}
            >
              <div
                style={{
                  width: `${filledPercent}%`,
                  height: "100%",
                  background: availabilityColors.fg,
                }}
              />
            </div>

            <div style={{ fontSize: "12px", color: "#64748b", marginTop: "8px" }}>
              {summary.occupied} occupied - {summary.reserved} reserved
            </div>
          </>
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "7px",
              fontSize: "13px",
              color: "#64748b",
            }}
          >
            <Armchair size={17} />
            Seat availability not published yet
          </div>
        )}
      </div>

      {/* Starting price */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "7px",
          fontSize: "14px",
          color: "#334155",
        }}
      >
        <Tag size={16} color="#475569" />
        {startingPlan ? (
          <span>
            Starting from{" "}
            <strong style={{ color: "#0f172a" }}>
              ₹{formatPrice(startingPlan.price)}
            </strong>
            /{formatDuration(startingPlan.duration_days)}
          </span>
        ) : (
          <span style={{ color: "#64748b" }}>Pricing not available</span>
        )}
      </div>

      {/* Explore â€” FR-04 route, not built yet */}
      <Link
        href={`/student/library/${library.id}`}
        style={{
          marginTop: "auto",
          display: "block",
          textAlign: "center",
          background: "#2563eb",
          color: "#ffffff",
          borderRadius: "8px",
          padding: "11px",
          fontSize: "14px",
          fontWeight: 700,
        }}
      >
        Explore
      </Link>
    </div>
  );
}



