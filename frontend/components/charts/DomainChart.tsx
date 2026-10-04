"use client";

import React, { useMemo } from "react";
import { GraduationCap, Users } from "lucide-react";

interface DomainChartProps {
  domains?: string[];
  breakdown?: Array<{ domain: string; count: number }>;
  totalCount?: number;
}

const DOMAIN_COLORS: Record<string, { bg: string; bar: string; text: string }> = {
  UPSC: { bg: "#eff6ff", bar: "#2563eb", text: "#1d4ed8" },
  SSC: { bg: "#f0fdf4", bar: "#16a34a", text: "#15803d" },
  NEET: { bg: "#fefce8", bar: "#ca8a04", text: "#a16207" },
  JEE: { bg: "#faf5ff", bar: "#9333ea", text: "#7e22ce" },
  GATE: { bg: "#fff7ed", bar: "#ea580c", text: "#c2410c" },
  CA: { bg: "#fdf2f8", bar: "#db2777", text: "#be185d" },
  Banking: { bg: "#ecfeff", bar: "#0891b2", text: "#0e7490" },
  CAT: { bg: "#f0fdfa", bar: "#0d9488", text: "#0f766e" },
  "State PSC": { bg: "#f5f3ff", bar: "#7c3aed", text: "#6d28d9" },
  "General Study": { bg: "#f1f5f9", bar: "#64748b", text: "#475569" },
};

const DEFAULT_COLOR = { bg: "#eff6ff", bar: "#3b82f6", text: "#1d4ed8" };

export default function DomainChart({
  domains = [],
  breakdown = [],
  totalCount,
}: DomainChartProps) {
  // Combine breakdown data or generate distribution from domains list
  const data = useMemo(() => {
    if (breakdown && breakdown.length > 0) {
      const sum = breakdown.reduce((acc, curr) => acc + curr.count, 0);
      const computedTotal = totalCount || sum || 1;
      return breakdown.map((item) => ({
        domain: item.domain,
        count: item.count,
        percentage: sum > 0 ? Math.round((item.count / computedTotal) * 100) : 0,
      }));
    }

    if (domains && domains.length > 0) {
      // Catered domain tags when members haven't joined yet
      return domains.map((domain) => ({
        domain,
        count: 0,
        percentage: 0,
      }));
    }

    return [];
  }, [domains, breakdown, totalCount]);

  if (data.length === 0) {
    return (
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "14px",
          padding: "20px",
          textAlign: "center",
          color: "#64748b",
        }}
      >
        <GraduationCap size={32} color="#94a3b8" style={{ margin: "0 auto 8px" }} />
        <p style={{ fontSize: "14px" }}>No competitive exam domains listed for this library.</p>
      </div>
    );
  }

  const hasNonZeroCounts = data.some((d) => d.count > 0);

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        borderRadius: "14px",
        padding: "22px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <GraduationCap size={20} color="#2563eb" />
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a" }}>
            Aspirant Peer Community Breakdown
          </h3>
        </div>
        <span style={{ fontSize: "12px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
          <Users size={14} />
          {hasNonZeroCounts ? "Active Members" : "Domains Catered"}
        </span>
      </div>

      <p style={{ fontSize: "13px", color: "#64748b", marginBottom: "16px" }}>
        {hasNonZeroCounts
          ? "See the current distribution of competitive exam aspirants studying at this branch."
          : "This library provides curated seating, quiet zones, and resources for the following streams:"}
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {data.map((item) => {
          const colorConfig = DOMAIN_COLORS[item.domain] || DEFAULT_COLOR;
          const displayWidth = hasNonZeroCounts
            ? Math.max(item.percentage, 6)
            : 100 / data.length;

          return (
            <div key={item.domain}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "13px",
                  fontWeight: "600",
                  marginBottom: "4px",
                }}
              >
                <span style={{ color: "#334155" }}>{item.domain}</span>
                <span style={{ color: colorConfig.text }}>
                  {hasNonZeroCounts ? `${item.count} members (${item.percentage}%)` : "Catered"}
                </span>
              </div>
              <div
                style={{
                  height: "8px",
                  background: "#f1f5f9",
                  borderRadius: "4px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${displayWidth}%`,
                    background: colorConfig.bar,
                    borderRadius: "4px",
                    transition: "width 0.4s ease",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
