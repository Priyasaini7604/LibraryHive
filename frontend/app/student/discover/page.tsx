"use client";

import React, { FormEvent, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { Library } from "@/lib/types";
import LibraryCard from "@/components/LibraryCard";
import {
  Search,
  LocateFixed,
  AlertCircle,
  Loader2,
  SearchX,
  X,
} from "lucide-react";

// Same domain names the owner setup page offers. The API matches them
// against each library's comma-separated domains_catered text.
const DOMAINS = [
  "UPSC",
  "SSC",
  "NEET",
  "JEE",
  "GATE",
  "CA",
  "Banking",
  "CAT",
  "State PSC",
  "General Study",
];

const RADIUS_OPTIONS_KM = [5, 10, 25, 50, 100];

const controlStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: "8px",
  border: "1px solid #cbd5e1",
  fontSize: "14px",
  background: "#ffffff",
  outline: "none",
};

export default function StudentDiscoverPage() {
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // Search / filter state. `searchInput` is what is typed; `search` is what
  // has been submitted to the backend.
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState("");

  // Location is optional. Without it the list simply has no distances.
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(
    null
  );
  const [radius, setRadius] = useState(25);
  const [isLocating, setIsLocating] = useState(false);
  const [locationMessage, setLocationMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setIsLoading(true);
      setError("");
      try {
        const data = await apiClient.getLibraries({
          search: search || undefined,
          domain: domain || undefined,
          ...(coords ? { lat: coords.lat, lng: coords.lng, radius } : {}),
        });
        if (!cancelled) setLibraries(data);
      } catch (err: any) {
        if (!cancelled) {
          setLibraries([]);
          setError(err.message || "Failed to load libraries.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [search, domain, coords, radius, reloadKey]);

  const handleSearch = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSearch(searchInput.trim());
  };

  const handleUseLocation = () => {
    setLocationMessage("");

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setLocationMessage("Your browser does not support location access.");
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
        setIsLocating(false);
      },
      (geoError) => {
        setIsLocating(false);
        setLocationMessage(
          geoError.code === geoError.PERMISSION_DENIED
            ? "Location permission was denied. Showing libraries without distance."
            : "Could not get your location. Showing libraries without distance."
        );
      },
      { timeout: 10000 }
    );
  };

  const clearLocation = () => {
    setCoords(null);
    setLocationMessage("");
  };

  const hasFilters = !!(search || domain || coords);

  const clearAll = () => {
    setSearchInput("");
    setSearch("");
    setDomain("");
    clearLocation();
  };

  return (
    <div
      style={{
        minHeight: "calc(100vh - 67px)",
        background: "#f8fafc",
        padding: "32px 20px",
      }}
    >
      <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
        <h1
          style={{
            fontSize: "26px",
            fontWeight: 800,
            color: "#0f172a",
            margin: 0,
          }}
        >
          Library Discovery
        </h1>
        <p style={{ fontSize: "14px", color: "#64748b", marginTop: "6px" }}>
          Find a study library, check live seat availability and pricing.
        </p>

        {/* Controls */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "10px",
            marginTop: "22px",
          }}
        >
          <form
            onSubmit={handleSearch}
            style={{
              display: "flex",
              gap: "8px",
              flex: "1 1 280px",
              minWidth: 0,
            }}
          >
            <div style={{ position: "relative", flex: 1, minWidth: 0 }}>
              <Search
                size={17}
                color="#94a3b8"
                style={{
                  position: "absolute",
                  left: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by library name or area..."
                aria-label="Search libraries"
                style={{
                  ...controlStyle,
                  width: "100%",
                  paddingLeft: "38px",
                }}
              />
            </div>
            <button
              type="submit"
              style={{
                ...controlStyle,
                background: "#2563eb",
                color: "#ffffff",
                border: "none",
                fontWeight: 700,
              }}
            >
              Search
            </button>
          </form>

          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            aria-label="Filter by domain"
            style={controlStyle}
          >
            <option value="">All domains</option>
            {DOMAINS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={handleUseLocation}
            disabled={isLocating}
            style={{
              ...controlStyle,
              display: "flex",
              alignItems: "center",
              gap: "7px",
              fontWeight: 600,
              color: "#2563eb",
              borderColor: "#2563eb",
              cursor: isLocating ? "not-allowed" : "pointer",
            }}
          >
            {isLocating ? <Loader2 size={16} /> : <LocateFixed size={16} />}
            {isLocating ? "Locating..." : "Use my location"}
          </button>
        </div>

        {/* Active location */}
        {coords && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "10px",
              marginTop: "12px",
              fontSize: "13px",
              color: "#334155",
            }}
          >
            <span>Showing libraries within</span>
            <select
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              aria-label="Search radius"
              style={{ ...controlStyle, padding: "6px 10px" }}
            >
              {RADIUS_OPTIONS_KM.map((km) => (
                <option key={km} value={km}>
                  {km} km
                </option>
              ))}
            </select>
            <span>of your location, nearest first.</span>
            <button
              type="button"
              onClick={clearLocation}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                background: "none",
                border: "none",
                color: "#64748b",
                fontSize: "13px",
              }}
            >
              <X size={14} /> Clear location
            </button>
          </div>
        )}

        {locationMessage && (
          <div
            style={{
              marginTop: "12px",
              fontSize: "13px",
              color: "#92400e",
              background: "#fef3c7",
              border: "1px solid #fde68a",
              borderRadius: "8px",
              padding: "10px 12px",
            }}
          >
            {locationMessage}
          </div>
        )}

        {/* Results */}
        <div style={{ marginTop: "24px" }}>
          {isLoading ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "10px",
                padding: "60px 0",
                color: "#64748b",
                fontSize: "15px",
              }}
            >
              <Loader2 size={20} />
              Loading libraries...
            </div>
          ) : error ? (
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
                <div style={{ fontWeight: 700 }}>Could not load libraries</div>
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
          ) : libraries.length === 0 ? (
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "12px",
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
                No libraries found
              </div>
              <p style={{ fontSize: "14px", marginTop: "6px" }}>
                {hasFilters
                  ? "Try a different search, domain, or a larger radius."
                  : "No libraries have been added yet."}
              </p>
              {hasFilters && (
                <button
                  type="button"
                  onClick={clearAll}
                  style={{
                    marginTop: "14px",
                    background: "#2563eb",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "8px",
                    padding: "9px 18px",
                    fontSize: "14px",
                    fontWeight: 600,
                  }}
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            <>
              <div
                style={{
                  fontSize: "13px",
                  color: "#64748b",
                  marginBottom: "14px",
                }}
              >
                {libraries.length}{" "}
                {libraries.length === 1 ? "library" : "libraries"} found
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(min(300px, 100%), 1fr))",
                  gap: "18px",
                }}
              >
                {libraries.map((library) => (
                  <LibraryCard key={library.id} library={library} />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
