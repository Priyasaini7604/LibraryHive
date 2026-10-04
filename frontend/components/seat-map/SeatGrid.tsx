"use client";

import React, { useState, useMemo } from "react";
import { Seat, SeatStatus } from "@/lib/types";
import { Check, Armchair, Search, Filter, Clock, AlertCircle } from "lucide-react";

interface SeatGridProps {
  seats: Seat[];
  selectedSeatId?: string | null;
  onSelectSeat?: (seat: Seat) => void;
  interactive?: boolean;
  activeShift?: string;
  onShiftChange?: (shift: string) => void;
}

const SHIFTS = [
  { id: "full_day", label: "Full Day (24/12h)", hours: "06:00 AM - 11:00 PM" },
  { id: "morning", label: "Morning Shift", hours: "06:00 AM - 02:00 PM" },
  { id: "evening", label: "Evening Shift", hours: "02:00 PM - 10:00 PM" },
  { id: "night", label: "Night Shift", hours: "10:00 PM - 06:00 AM" },
];

export default function SeatGrid({
  seats = [],
  selectedSeatId,
  onSelectSeat,
  interactive = true,
  activeShift = "full_day",
  onShiftChange,
}: SeatGridProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | SeatStatus>("all");

  // Summary counts
  const summary = useMemo(() => {
    const total = seats.length;
    const empty = seats.filter((s) => s.status === "empty").length;
    const reserved = seats.filter((s) => s.status === "reserved").length;
    const occupied = seats.filter((s) => s.status === "occupied").length;
    return { total, empty, reserved, occupied };
  }, [seats]);

  // Group seats by row
  const groupedSeats = useMemo(() => {
    const groups: Record<string, Seat[]> = {};

    seats.forEach((seat) => {
      // Apply search query filter
      if (searchQuery.trim() && !seat.label.toLowerCase().includes(searchQuery.toLowerCase())) {
        return;
      }
      // Apply status filter
      if (statusFilter !== "all" && seat.status !== statusFilter) {
        return;
      }

      // Extract row name from formats like "Row A - Seat 1", "Row A", "A1", or fallback
      let rowKey = "General";
      const matchRow = seat.label.match(/Row\s+([A-Za-z0-9]+)/i);
      const matchAlpha = seat.label.match(/^([A-Za-z]+)\s*\d+/);

      if (matchRow && matchRow[1]) {
        rowKey = `Row ${matchRow[1].toUpperCase()}`;
      } else if (matchAlpha && matchAlpha[1]) {
        rowKey = `Row ${matchAlpha[1].toUpperCase()}`;
      }

      if (!groups[rowKey]) {
        groups[rowKey] = [];
      }
      groups[rowKey].push(seat);
    });

    // Sort rows alphabetically
    return Object.keys(groups)
      .sort()
      .reduce((acc, key) => {
        acc[key] = groups[key];
        return acc;
      }, {} as Record<string, Seat[]>);
  }, [seats, searchQuery, statusFilter]);

  const selectedSeat = useMemo(
    () => seats.find((s) => s.id === selectedSeatId) || null,
    [seats, selectedSeatId]
  );

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        borderRadius: "16px",
        padding: "24px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}
    >
      {/* Top Controls: Shift Selector & Live Summary */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "20px",
          borderBottom: "1px solid #f1f5f9",
          paddingBottom: "16px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
            <Clock size={18} color="#2563eb" />
            <span style={{ fontSize: "14px", fontWeight: "600", color: "#0f172a" }}>
              Operational Shift:
            </span>
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {SHIFTS.map((s) => {
              const isSelected = activeShift === s.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => onShiftChange && onShiftChange(s.id)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "8px",
                    fontSize: "13px",
                    fontWeight: isSelected ? "600" : "500",
                    border: `1px solid ${isSelected ? "#2563eb" : "#cbd5e1"}`,
                    background: isSelected ? "#eff6ff" : "#ffffff",
                    color: isSelected ? "#1d4ed8" : "#475569",
                    cursor: onShiftChange ? "pointer" : "default",
                    transition: "all 0.15s ease",
                  }}
                  title={s.hours}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Live Counters */}
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <div
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              background: "#ecfdf5",
              border: "1px solid #a7f3d0",
              color: "#065f46",
              fontSize: "13px",
              fontWeight: "600",
            }}
          >
            🟢 {summary.empty} Available
          </div>
          <div
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              background: "#fffbeb",
              border: "1px solid #fde68a",
              color: "#92400e",
              fontSize: "13px",
              fontWeight: "600",
            }}
          >
            🟡 {summary.reserved} Reserved
          </div>
          <div
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#991b1b",
              fontSize: "13px",
              fontWeight: "600",
            }}
          >
            🔴 {summary.occupied} Occupied
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          marginBottom: "20px",
        }}
      >
        {/* Search */}
        <div style={{ position: "relative", minWidth: "220px", flex: "1" }}>
          <Search
            size={16}
            color="#94a3b8"
            style={{ position: "absolute", left: "10px", top: "10px" }}
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search seat number (e.g. A-1)..."
            style={{
              width: "100%",
              padding: "8px 12px 8px 32px",
              borderRadius: "8px",
              border: "1px solid #cbd5e1",
              fontSize: "13px",
            }}
          />
        </div>

        {/* Status Filter Tabs */}
        <div style={{ display: "flex", gap: "6px" }}>
          {(
            [
              { key: "all", label: "All Seats" },
              { key: "empty", label: "Available Only" },
              { key: "occupied", label: "Occupied" },
              { key: "reserved", label: "Reserved" },
            ] as const
          ).map((tab) => {
            const isActive = statusFilter === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setStatusFilter(tab.key)}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: isActive ? "600" : "500",
                  background: isActive ? "#0f172a" : "#f1f5f9",
                  color: isActive ? "#ffffff" : "#475569",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Front of Hall / Whiteboard Indicator */}
      <div
        style={{
          textAlign: "center",
          background: "#f8fafc",
          border: "1px dashed #cbd5e1",
          borderRadius: "8px",
          padding: "8px",
          marginBottom: "28px",
          fontSize: "12px",
          fontWeight: "700",
          color: "#64748b",
          letterSpacing: "1.5px",
          textTransform: "uppercase",
        }}
      >
        📖 Front of Room / Quiet Study Hall Board 📖
      </div>

      {/* Empty State */}
      {seats.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "40px 20px",
            background: "#f8fafc",
            borderRadius: "12px",
            color: "#64748b",
          }}
        >
          <Armchair size={40} color="#94a3b8" style={{ margin: "0 auto 12px" }} />
          <h4 style={{ fontSize: "16px", fontWeight: "600", color: "#334155", marginBottom: "4px" }}>
            No seats configured yet
          </h4>
          <p style={{ fontSize: "13px" }}>
            The library owner has not configured the seat layout for this library.
          </p>
        </div>
      ) : Object.keys(groupedSeats).length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "36px 20px",
            background: "#f8fafc",
            borderRadius: "12px",
            color: "#64748b",
          }}
        >
          <AlertCircle size={32} color="#94a3b8" style={{ margin: "0 auto 8px" }} />
          <p style={{ fontSize: "14px", fontWeight: "500" }}>
            No seats match your search or filter criteria.
          </p>
        </div>
      ) : (
        /* Seat Layout Grid by Row */
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {Object.entries(groupedSeats).map(([rowName, rowSeats]) => (
            <div
              key={rowName}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "16px",
                flexWrap: "wrap",
              }}
            >
              {/* Row Label */}
              <div
                style={{
                  width: "70px",
                  fontSize: "13px",
                  fontWeight: "700",
                  color: "#475569",
                  paddingTop: "12px",
                  flexShrink: 0,
                }}
              >
                {rowName}
              </div>

              {/* Seats in this row */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))",
                  gap: "10px",
                  flex: "1",
                }}
              >
                {rowSeats.map((seat) => {
                  const isSelected = selectedSeatId === seat.id;
                  const isAvailable = seat.status === "empty";
                  const isReserved = seat.status === "reserved";
                  const isOccupied = seat.status === "occupied";

                  // Seat Styling based on status and selection
                  let bg = "#ecfdf5";
                  let border = "#10b981";
                  let textColor = "#065f46";
                  let cursor = interactive && isAvailable ? "pointer" : "not-allowed";

                  if (isReserved) {
                    bg = "#fffbeb";
                    border = "#f59e0b";
                    textColor = "#92400e";
                  } else if (isOccupied) {
                    bg = "#fef2f2";
                    border = "#ef4444";
                    textColor = "#991b1b";
                  }

                  if (isSelected) {
                    bg = "#2563eb";
                    border = "#1d4ed8";
                    textColor = "#ffffff";
                  }

                  return (
                    <button
                      key={seat.id}
                      type="button"
                      disabled={!interactive || !isAvailable}
                      onClick={() => {
                        if (interactive && isAvailable && onSelectSeat) {
                          onSelectSeat(seat);
                        }
                      }}
                      style={{
                        padding: "10px 6px",
                        borderRadius: "10px",
                        border: `2px solid ${border}`,
                        background: bg,
                        color: textColor,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "4px",
                        cursor,
                        transition: "all 0.15s ease",
                        position: "relative",
                        outline: isSelected ? "3px solid #93c5fd" : "none",
                        boxShadow: isSelected
                          ? "0 4px 6px -1px rgba(37, 99, 235, 0.2)"
                          : "0 1px 2px rgba(0,0,0,0.04)",
                      }}
                      title={`${seat.label} — ${seat.status.toUpperCase()}${
                        isAvailable ? " (Click to Select)" : ""
                      }`}
                    >
                      <Armchair size={18} />
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: "700",
                          textAlign: "center",
                          wordBreak: "break-word",
                          lineHeight: "1.2",
                        }}
                      >
                        {seat.label.replace(/^Row\s+[A-Za-z0-9]+\s*-\s*/i, "")}
                      </span>
                      <span
                        style={{
                          fontSize: "9px",
                          fontWeight: "600",
                          textTransform: "uppercase",
                          opacity: 0.9,
                        }}
                      >
                        {isSelected ? "Selected" : seat.status}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Interactive Legend & Selected Seat Indicator */}
      <div
        style={{
          marginTop: "24px",
          paddingTop: "16px",
          borderTop: "1px solid #f1f5f9",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "14px",
        }}
      >
        {/* Color Legend */}
        <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", fontSize: "12px", color: "#475569" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <div
              style={{
                width: "14px",
                height: "14px",
                borderRadius: "4px",
                background: "#ecfdf5",
                border: "2px solid #10b981",
              }}
            />
            <span>Available (Empty)</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <div
              style={{
                width: "14px",
                height: "14px",
                borderRadius: "4px",
                background: "#fffbeb",
                border: "2px solid #f59e0b",
              }}
            />
            <span>Reserved (Hold)</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <div
              style={{
                width: "14px",
                height: "14px",
                borderRadius: "4px",
                background: "#fef2f2",
                border: "2px solid #ef4444",
              }}
            />
            <span>Occupied (Member)</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <div
              style={{
                width: "14px",
                height: "14px",
                borderRadius: "4px",
                background: "#2563eb",
                border: "2px solid #1d4ed8",
              }}
            />
            <span style={{ fontWeight: "600", color: "#1d4ed8" }}>Your Selection</span>
          </div>
        </div>

        {/* Selected Seat Tag */}
        {selectedSeat && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              padding: "6px 14px",
              borderRadius: "20px",
              fontSize: "13px",
              fontWeight: "600",
              color: "#1d4ed8",
            }}
          >
            <Check size={16} />
            <span>Selected: {selectedSeat.label}</span>
          </div>
        )}
      </div>
    </div>
  );
}
