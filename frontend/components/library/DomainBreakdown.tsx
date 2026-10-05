import React from "react";
import { BarChart3 } from "lucide-react";
import { DomainBreakdown as DomainBreakdownData } from "@/lib/types";

interface DomainBreakdownProps {
  /**
   * Aggregated current members by domain. Left undefined until the backend
   * endpoint exists; the component then shows an honest "not available" state.
   */
  data?: DomainBreakdownData | null;
  isLoading?: boolean;
  error?: string;
}

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "22px",
  boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
};

const messageStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  marginTop: "16px",
  fontSize: "14px",
  color: "#94a3b8",
};

export default function DomainBreakdown({
  data,
  isLoading = false,
  error = "",
}: DomainBreakdownProps) {
  const items = data
    ? [...data.breakdown].sort((a, b) => b.count - a.count)
    : [];
  const total = data ? data.total_members : 0;

  let body: React.ReactNode;

  if (isLoading) {
    body = <div style={messageStyle}>Loading member breakdown...</div>;
  } else if (error) {
    body = (
      <div role="alert" style={{ ...messageStyle, color: "#991b1b" }}>
        {error}
      </div>
    );
  } else if (!data) {
    body = (
      <div style={messageStyle}>
        <BarChart3 size={16} />
        Member breakdown is not available yet.
      </div>
    );
  } else if (total === 0 || items.length === 0) {
    body = (
      <div style={messageStyle}>
        <BarChart3 size={16} />
        No current members yet.
      </div>
    );
  } else {
    body = (
      <>
        <div style={{ fontSize: "13px", color: "#64748b", marginTop: "6px" }}>
          {total} current {total === 1 ? "member" : "members"}
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            marginTop: "16px",
          }}
        >
          {items.map((item) => {
            const percent = Math.round((item.count / total) * 100);
            return (
              <div key={item.domain}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: "10px",
                    fontSize: "13px",
                    color: "#334155",
                    marginBottom: "5px",
                  }}
                >
                  <span style={{ fontWeight: 600 }}>{item.domain}</span>
                  <span style={{ color: "#64748b" }}>
                    {item.count} ({percent}%)
                  </span>
                </div>
                <div
                  style={{
                    height: "8px",
                    background: "#e2e8f0",
                    borderRadius: "999px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${percent}%`,
                      height: "100%",
                      background: "#2563eb",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </>
    );
  }

  return (
    <section style={cardStyle}>
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
        Who studies here
      </h2>
      {body}
    </section>
  );
}
