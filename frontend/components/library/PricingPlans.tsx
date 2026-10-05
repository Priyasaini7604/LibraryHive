import React from "react";
import { Tag } from "lucide-react";
import { PricingPlan } from "@/lib/types";

interface PricingPlansProps {
  plans?: PricingPlan[];
}

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "22px",
  boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
};

const formatPrice = (price: number | string) =>
  Number(price).toLocaleString("en-IN");

const formatDuration = (days: number) =>
  days === 30 ? "1 month" : days === 365 ? "1 year" : `${days} days`;

export default function PricingPlans({ plans }: PricingPlansProps) {
  const validPlans = (plans || []).filter((p) => !Number.isNaN(Number(p.price)));

  const lowestPrice = validPlans.length
    ? Math.min(...validPlans.map((p) => Number(p.price)))
    : null;

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
        Pricing plans
      </h2>

      {validPlans.length === 0 ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginTop: "16px",
            fontSize: "14px",
            color: "#94a3b8",
          }}
        >
          <Tag size={16} />
          Pricing plans have not been published yet.
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            marginTop: "16px",
          }}
        >
          {validPlans.map((plan, index) => {
            const isLowest =
              validPlans.length > 1 && Number(plan.price) === lowestPrice;

            return (
              <div
                key={plan.id || `${plan.name}-${index}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  flexWrap: "wrap",
                  border: isLowest ? "1px solid #bfdbfe" : "1px solid #e2e8f0",
                  background: isLowest ? "#eff6ff" : "#f8fafc",
                  borderRadius: "10px",
                  padding: "12px 14px",
                }}
              >
                <div>
                  <div
                    style={{ fontSize: "15px", fontWeight: 700, color: "#0f172a" }}
                  >
                    {plan.name}
                  </div>
                  <div style={{ fontSize: "13px", color: "#64748b", marginTop: "2px" }}>
                    {formatDuration(plan.duration_days)}
                  </div>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div
                    style={{ fontSize: "18px", fontWeight: 800, color: "#0f172a" }}
                  >
                    ₹{formatPrice(plan.price)}
                  </div>
                  {isLowest && (
                    <div
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#1d4ed8",
                        marginTop: "2px",
                      }}
                    >
                      Lowest price
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
