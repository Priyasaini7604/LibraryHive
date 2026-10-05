"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { Library } from "@/lib/types";
import LibraryInfo from "@/components/library/LibraryInfo";
import PricingPlans from "@/components/library/PricingPlans";
import DomainBreakdown from "@/components/library/DomainBreakdown";
import SeatMapSection from "@/components/library/SeatMapSection";
import {
  ArrowLeft,
  AlertCircle,
  Loader2,
  SearchX,
  Sparkles,
} from "lucide-react";

const sectionCardStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "22px",
  boxShadow: "0 2px 10px rgba(15, 23, 42, 0.04)",
};

// The backend has no amenities field yet, so this is an honest placeholder.
function AmenitiesCard() {
  return (
    <section style={sectionCardStyle}>
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
        Amenities
      </h2>
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
        <Sparkles size={16} />
        Amenities not listed yet.
      </div>
    </section>
  );
}

export default function LibraryExplorePage() {
  const params = useParams();
  const rawId = params?.id;
  const id = Array.isArray(rawId) ? rawId[0] : rawId;

  const [library, setLibrary] = useState<Library | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    const load = async () => {
      setIsLoading(true);
      setNotFound(false);
      setError("");
      try {
        const data = await apiClient.getLibrary(id);
        if (!cancelled) setLibrary(data);
      } catch (err: any) {
        if (cancelled) return;
        setLibrary(null);
        if (err?.status === 404) {
          setNotFound(true);
        } else {
          const message = err?.message;
          setError(
            message && message !== "null"
              ? message
              : "Failed to load this library."
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  const backLink = (
    <Link
      href="/student/discover"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontSize: "14px",
        fontWeight: 600,
        color: "#2563eb",
      }}
    >
      <ArrowLeft size={16} /> Back to libraries
    </Link>
  );

  let content: React.ReactNode;

  if (isLoading) {
    content = (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "10px",
          padding: "80px 0",
          color: "#64748b",
          fontSize: "15px",
        }}
      >
        <Loader2 size={20} />
        Loading library...
      </div>
    );
  } else if (notFound) {
    content = (
      <div
        style={{
          ...sectionCardStyle,
          padding: "50px 20px",
          textAlign: "center",
          color: "#64748b",
        }}
      >
        <SearchX size={34} color="#94a3b8" />
        <div
          style={{
            fontSize: "17px",
            fontWeight: 700,
            color: "#0f172a",
            marginTop: "10px",
          }}
        >
          Library not found
        </div>
        <p style={{ fontSize: "14px", marginTop: "6px" }}>
          This library does not exist or is no longer available.
        </p>
      </div>
    );
  } else if (error || !library) {
    content = (
      <div
        role="alert"
        style={{
          background: "#fee2e2",
          border: "1px solid #fecaca",
          color: "#991b1b",
          borderRadius: "10px",
          padding: "18px",
          display: "flex",
          alignItems: "flex-start",
          gap: "10px",
          fontSize: "14px",
        }}
      >
        <AlertCircle size={19} style={{ flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700 }}>Could not load this library</div>
          <div style={{ marginTop: "4px" }}>
            {error || "Something went wrong."}
          </div>
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
  } else {
    content = (
      <>
        <h1
          style={{
            fontSize: "28px",
            fontWeight: 800,
            color: "#0f172a",
            margin: "0 0 18px",
          }}
        >
          {library.name}
        </h1>

        <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          <LibraryInfo library={library} />

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(min(300px, 100%), 1fr))",
              gap: "18px",
              alignItems: "start",
            }}
          >
            <PricingPlans plans={library.plans} />
            <AmenitiesCard />
            {/* No data prop yet: the member-by-domain endpoint does not exist. */}
            <DomainBreakdown />
          </div>

          <SeatMapSection libraryId={library.id} />
        </div>
      </>
    );
  }

  return (
    <div
      style={{
        minHeight: "calc(100vh - 67px)",
        background: "#f8fafc",
        padding: "32px 20px",
      }}
    >
      <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
        <div style={{ marginBottom: "18px" }}>{backLink}</div>
        {content}
      </div>
    </div>
  );
}
