import "./globals.css";
import React from "react";

export const metadata = {
  title: "LibraryHive - Library Management Platform",
  description: "Library and Seat Management Platform for Owners and Students",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header
          style={{
            background: "#ffffff",
            borderBottom: "1px solid #e2e8f0",
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "34px",
                height: "34px",
                borderRadius: "8px",
                background: "#2563eb",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: "bold",
                fontSize: "18px",
              }}
            >
              LH
            </div>
            <span style={{ fontSize: "19px", fontWeight: "700", color: "#0f172a" }}>
              Library<span style={{ color: "#2563eb" }}>Hive</span>
            </span>
          </div>
          <div style={{ fontSize: "14px", color: "#64748b" }}>
            Owner Workspace
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
