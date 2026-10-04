import "./globals.css";
import React from "react";

export const metadata = {
  title: "LibraryHive - Library Management Platform",
  description: "Library and Seat Management Platform for Owners and Students",
};

import Link from "next/link";

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
            padding: "14px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <Link
            href="/student/discover"
            style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}
          >
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
          </Link>

          <nav style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <Link
              href="/student/discover"
              style={{
                fontSize: "14px",
                fontWeight: "600",
                color: "#2563eb",
                background: "#eff6ff",
                padding: "6px 14px",
                borderRadius: "8px",
                textDecoration: "none",
              }}
            >
              🔍 Discover Libraries
            </Link>
            <Link
              href="/owner/setup"
              style={{
                fontSize: "14px",
                fontWeight: "500",
                color: "#475569",
                padding: "6px 12px",
                borderRadius: "8px",
                textDecoration: "none",
              }}
            >
              ⚙️ Owner Setup
            </Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

