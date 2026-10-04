"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { Library } from "@/lib/types";
import {
  Search,
  MapPin,
  Clock,
  DollarSign,
  Armchair,
  Filter,
  Navigation,
  Compass,
  ArrowRight,
  RotateCcw,
  Sparkles,
  Wifi,
  Wind,
  Zap,
  Coffee,
  AlertCircle,
} from "lucide-react";

const POPULAR_DOMAINS = [
  "All",
  "UPSC",
  "SSC",
  "NEET",
  "JEE",
  "GATE",
  "CA",
  "Banking",
  "CAT",
  "State PSC",
];

const CITY_PRESETS = [
  { name: "Delhi (Connaught Place)", lat: 28.6315, lng: 77.2167 },
  { name: "Noida (Sector 62)", lat: 28.628, lng: 77.3649 },
  { name: "South Delhi", lat: 28.5684, lng: 77.2217 },
  { name: "Jaipur", lat: 26.9124, lng: 75.7873 },
  { name: "Lucknow", lat: 26.8467, lng: 80.9462 },
];

export default function StudentDiscoverPage() {
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Search & Filter State
  const [searchText, setSearchText] = useState("");
  const [selectedDomain, setSelectedDomain] = useState("All");
  const [userLat, setUserLat] = useState<number | null>(null);
  const [userLng, setUserLng] = useState<number | null>(null);
  const [searchRadius, setSearchRadius] = useState<number>(10);
  const [isLocating, setIsLocating] = useState(false);
  const [locationName, setLocationName] = useState<string | null>(null);

  // Sort State
  const [sortBy, setSortBy] = useState<"distance" | "empty_seats" | "price">("distance");

  const fetchLibraries = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const params: {
        search?: string;
        domain?: string;
        lat?: number;
        lng?: number;
        radius?: number;
      } = {};

      if (searchText.trim()) {
        params.search = searchText.trim();
      }
      if (selectedDomain !== "All") {
        params.domain = selectedDomain;
      }
      if (userLat !== null && userLng !== null) {
        params.lat = userLat;
        params.lng = userLng;
        params.radius = searchRadius;
      }

      const data = await apiClient.getLibraries(params);
      setLibraries(data);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load libraries. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, [searchText, selectedDomain, userLat, userLng, searchRadius]);

  useEffect(() => {
    fetchLibraries();
  }, [fetchLibraries]);

  // Request browser geolocation
  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLat(pos.coords.latitude);
        setUserLng(pos.coords.longitude);
        setLocationName("Your Current Location");
        setIsLocating(false);
      },
      (err) => {
        console.warn("Geolocation error", err);
        setIsLocating(false);
        // Fallback to Delhi default
        setUserLat(28.6139);
        setUserLng(77.209);
        setLocationName("Delhi (Default GPS)");
      },
      { timeout: 10000 }
    );
  };

  const handleSelectCityPreset = (city: (typeof CITY_PRESETS)[0]) => {
    setUserLat(city.lat);
    setUserLng(city.lng);
    setLocationName(city.name);
  };

  const handleClearLocation = () => {
    setUserLat(null);
    setUserLng(null);
    setLocationName(null);
  };

  const handleResetFilters = () => {
    setSearchText("");
    setSelectedDomain("All");
    setUserLat(null);
    setUserLng(null);
    setLocationName(null);
    setSearchRadius(10);
  };

  // Sorted libraries
  const sortedLibraries = [...libraries].sort((a, b) => {
    if (sortBy === "distance") {
      return (a.distance_km ?? 9999) - (b.distance_km ?? 9999);
    }
    if (sortBy === "empty_seats") {
      const emptyA = a.seat_summary?.empty ?? 0;
      const emptyB = b.seat_summary?.empty ?? 0;
      return emptyB - emptyA;
    }
    if (sortBy === "price") {
      const priceA = a.starting_price ?? (a.plans?.[0]?.price ? Number(a.plans[0].price) : 99999);
      const priceB = b.starting_price ?? (b.plans?.[0]?.price ? Number(b.plans[0].price) : 99999);
      return Number(priceA) - Number(priceB);
    }
    return 0;
  });

  return (
    <div style={{ maxWidth: "1200px", margin: "28px auto", padding: "0 20px" }}>
      {/* Hero Banner */}
      <div
        style={{
          background: "linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)",
          borderRadius: "20px",
          padding: "36px 32px",
          color: "#ffffff",
          marginBottom: "32px",
          boxShadow: "0 10px 25px -5px rgba(37, 99, 235, 0.25)",
        }}
      >
        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "rgba(255,255,255,0.15)", padding: "6px 14px", borderRadius: "20px", fontSize: "12px", fontWeight: "600", marginBottom: "16px" }}>
          <Sparkles size={14} />
          <span>Real-Time Study Room & Seat Discovery</span>
        </div>
        <h1 style={{ fontSize: "32px", fontWeight: "800", marginBottom: "10px", lineHeight: "1.2" }}>
          Find Your Ideal Study Sanctuary
        </h1>
        <p style={{ fontSize: "16px", color: "#bfdbfe", maxWidth: "700px", lineHeight: "1.5" }}>
          Explore nearby self-study libraries, inspect live visual floor plans, see which exam peers study there, and reserve guaranteed quiet seats with air conditioning and power outlets.
        </p>
      </div>

      {/* Main Search & Control Hub */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "16px",
          padding: "24px",
          marginBottom: "32px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}
      >
        {/* Search Bar & Location Controls */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: "12px", marginBottom: "20px" }}>
          {/* Keyword Search */}
          <div style={{ position: "relative" }}>
            <Search size={18} color="#94a3b8" style={{ position: "absolute", left: "14px", top: "13px" }} />
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search by library name, area, or street address..."
              style={{
                width: "100%",
                padding: "11px 16px 11px 42px",
                borderRadius: "10px",
                border: "1px solid #cbd5e1",
                fontSize: "14px",
              }}
            />
          </div>

          {/* Current Location Button */}
          <button
            type="button"
            onClick={handleUseCurrentLocation}
            disabled={isLocating}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "11px 18px",
              borderRadius: "10px",
              border: "1px solid #93c5fd",
              background: userLat !== null ? "#eff6ff" : "#ffffff",
              color: userLat !== null ? "#1d4ed8" : "#2563eb",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            <Navigation size={16} />
            {isLocating ? "Detecting GPS..." : userLat !== null ? "GPS Active" : "Near Me"}
          </button>

          {/* Reset Filters */}
          {(searchText || selectedDomain !== "All" || userLat !== null) && (
            <button
              type="button"
              onClick={handleResetFilters}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "11px 16px",
                borderRadius: "10px",
                border: "1px solid #e2e8f0",
                background: "#f8fafc",
                color: "#64748b",
                fontWeight: "600",
                fontSize: "14px",
                cursor: "pointer",
              }}
              title="Reset all filters"
            >
              <RotateCcw size={16} />
              Reset
            </button>
          )}
        </div>

        {/* Location Indicator & Quick Presets */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "20px" }}>
          <span style={{ fontSize: "13px", fontWeight: "600", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
            <MapPin size={15} /> Location Preset:
          </span>
          {CITY_PRESETS.map((city) => {
            const isSelected = locationName === city.name;
            return (
              <button
                key={city.name}
                type="button"
                onClick={() => handleSelectCityPreset(city)}
                style={{
                  padding: "5px 12px",
                  borderRadius: "16px",
                  fontSize: "12px",
                  fontWeight: isSelected ? "600" : "500",
                  border: `1px solid ${isSelected ? "#2563eb" : "#e2e8f0"}`,
                  background: isSelected ? "#eff6ff" : "#ffffff",
                  color: isSelected ? "#1d4ed8" : "#475569",
                  cursor: "pointer",
                }}
              >
                {city.name}
              </button>
            );
          })}
          {userLat !== null && (
            <button
              type="button"
              onClick={handleClearLocation}
              style={{
                padding: "5px 10px",
                borderRadius: "16px",
                fontSize: "11px",
                color: "#ef4444",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                cursor: "pointer",
              }}
            >
              Clear Location ✕
            </button>
          )}
        </div>

        {/* Domain Filter Pills */}
        <div>
          <div style={{ fontSize: "13px", fontWeight: "600", color: "#334155", marginBottom: "8px" }}>
            Target Competitive Exam Domain:
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {POPULAR_DOMAINS.map((domain) => {
              const isSelected = selectedDomain === domain;
              return (
                <button
                  key={domain}
                  type="button"
                  onClick={() => setSelectedDomain(domain)}
                  style={{
                    padding: "7px 16px",
                    borderRadius: "20px",
                    fontSize: "13px",
                    fontWeight: isSelected ? "700" : "500",
                    border: `1px solid ${isSelected ? "#2563eb" : "#cbd5e1"}`,
                    background: isSelected ? "#2563eb" : "#ffffff",
                    color: isSelected ? "#ffffff" : "#475569",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {domain}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Results Header with Sorting */}
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
        <div>
          <h2 style={{ fontSize: "20px", fontWeight: "700", color: "#0f172a" }}>
            {locationName ? `Libraries near ${locationName}` : "All Registered Study Libraries"}
          </h2>
          <p style={{ fontSize: "13px", color: "#64748b" }}>
            Showing {sortedLibraries.length} verified {sortedLibraries.length === 1 ? "branch" : "branches"}
            {selectedDomain !== "All" && ` catering to ${selectedDomain}`}
          </p>
        </div>

        {/* Sorting Dropdown */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Filter size={15} color="#64748b" />
          <span style={{ fontSize: "13px", color: "#64748b" }}>Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              border: "1px solid #cbd5e1",
              fontSize: "13px",
              background: "#ffffff",
              color: "#334155",
            }}
          >
            <option value="distance">Proximity (Closest First)</option>
            <option value="empty_seats">Most Empty Seats</option>
            <option value="price">Lowest Starting Price</option>
          </select>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "24px" }}>
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "16px",
                padding: "24px",
                height: "280px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                animation: "pulse 1.5s infinite",
              }}
            >
              <div style={{ height: "24px", background: "#f1f5f9", borderRadius: "6px", width: "70%" }} />
              <div style={{ height: "16px", background: "#f1f5f9", borderRadius: "4px", width: "90%" }} />
              <div style={{ height: "16px", background: "#f1f5f9", borderRadius: "4px", width: "40%" }} />
              <div style={{ height: "40px", background: "#f1f5f9", borderRadius: "8px" }} />
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {errorMessage && !isLoading && (
        <div
          style={{
            background: "#fee2e2",
            border: "1px solid #fecaca",
            borderRadius: "12px",
            padding: "24px",
            textAlign: "center",
            color: "#991b1b",
          }}
        >
          <AlertCircle size={32} color="#dc2626" style={{ margin: "0 auto 10px" }} />
          <h3 style={{ fontSize: "16px", fontWeight: "700", marginBottom: "6px" }}>Unable to load libraries</h3>
          <p style={{ fontSize: "14px", marginBottom: "16px" }}>{errorMessage}</p>
          <button
            type="button"
            onClick={fetchLibraries}
            style={{
              background: "#dc2626",
              color: "#ffffff",
              padding: "8px 18px",
              borderRadius: "8px",
              border: "none",
              fontWeight: "600",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            Retry Fetch
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !errorMessage && sortedLibraries.length === 0 && (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "16px",
            padding: "48px 24px",
            textAlign: "center",
            color: "#64748b",
          }}
        >
          <Compass size={48} color="#94a3b8" style={{ margin: "0 auto 16px" }} />
          <h3 style={{ fontSize: "18px", fontWeight: "700", color: "#1e293b", marginBottom: "8px" }}>
            No study libraries found
          </h3>
          <p style={{ fontSize: "14px", maxWidth: "480px", margin: "0 auto 20px", lineHeight: "1.5" }}>
            We couldn&apos;t find any libraries matching your current search parameters or radius. Try widening your distance or clearing filters.
          </p>
          <button
            type="button"
            onClick={handleResetFilters}
            style={{
              background: "#2563eb",
              color: "#ffffff",
              padding: "10px 20px",
              borderRadius: "8px",
              border: "none",
              fontWeight: "600",
              fontSize: "14px",
              cursor: "pointer",
            }}
          >
            Reset Filters & View All
          </button>
        </div>
      )}

      {/* Library Cards Grid */}
      {!isLoading && !errorMessage && sortedLibraries.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(350px, 1fr))",
            gap: "24px",
          }}
        >
          {sortedLibraries.map((lib) => {
            const emptySeats = lib.seat_summary?.empty ?? 0;
            const totalSeats = lib.seat_summary?.total ?? lib.total_seats;
            const occupancyPct = totalSeats > 0 ? Math.round(((totalSeats - emptySeats) / totalSeats) * 100) : 0;
            const startingPrice = lib.starting_price ?? (lib.plans && lib.plans.length > 0 ? lib.plans[0].price : null);

            return (
              <div
                key={lib.id}
                style={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "16px",
                  overflow: "hidden",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
                  display: "flex",
                  flexDirection: "column",
                  transition: "transform 0.15s ease, box-shadow 0.15s ease",
                }}
              >
                {/* Card Top Banner */}
                <div
                  style={{
                    background: "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)",
                    padding: "20px 24px",
                    borderBottom: "1px solid #e2e8f0",
                    position: "relative",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px" }}>
                    <div>
                      <h3 style={{ fontSize: "19px", fontWeight: "700", color: "#0f172a", marginBottom: "4px" }}>
                        {lib.name}
                      </h3>
                      <p style={{ fontSize: "13px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                        <MapPin size={14} color="#2563eb" />
                        {lib.address}
                      </p>
                    </div>

                    {/* Distance Badge if available */}
                    {lib.distance_km !== undefined && (
                      <span
                        style={{
                          background: "#eff6ff",
                          border: "1px solid #bfdbfe",
                          color: "#1d4ed8",
                          fontSize: "12px",
                          fontWeight: "700",
                          padding: "4px 8px",
                          borderRadius: "8px",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {lib.distance_km} km away
                      </span>
                    )}
                  </div>
                </div>

                {/* Card Body */}
                <div style={{ padding: "20px 24px", flex: "1", display: "flex", flexDirection: "column", gap: "16px" }}>
                  {/* Real-time Seat Capacity Pill */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      background: emptySeats > 0 ? "#ecfdf5" : "#fef2f2",
                      border: `1px solid ${emptySeats > 0 ? "#a7f3d0" : "#fecaca"}`,
                      borderRadius: "10px",
                      padding: "10px 14px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Armchair size={18} color={emptySeats > 0 ? "#059669" : "#dc2626"} />
                      <div>
                        <div style={{ fontSize: "14px", fontWeight: "700", color: emptySeats > 0 ? "#065f46" : "#991b1b" }}>
                          {emptySeats > 0 ? `${emptySeats} Seats Available` : "Fully Occupied"}
                        </div>
                        <div style={{ fontSize: "11px", color: emptySeats > 0 ? "#047857" : "#b91c1c" }}>
                          Total Capacity: {totalSeats} Desks
                        </div>
                      </div>
                    </div>
                    <span style={{ fontSize: "12px", fontWeight: "600", color: emptySeats > 0 ? "#065f46" : "#991b1b" }}>
                      {occupancyPct}% filled
                    </span>
                  </div>

                  {/* Operational Details */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", fontSize: "13px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#475569" }}>
                      <Clock size={16} color="#64748b" />
                      <span>{lib.operating_hours || "08:00 AM - 10:00 PM"}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#059669", fontWeight: "600" }}>
                      <DollarSign size={16} color="#059669" />
                      <span>{startingPrice ? `From ₹${startingPrice}/mo` : "Custom Plans"}</span>
                    </div>
                  </div>

                  {/* Standard Facilities Badges */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                    {[
                      { icon: Wifi, label: "Fast WiFi" },
                      { icon: Wind, label: "AC" },
                      { icon: Zap, label: "Power Socket" },
                      { icon: Coffee, label: "Water RO" },
                    ].map((f, i) => {
                      const Icon = f.icon;
                      return (
                        <span
                          key={i}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            fontSize: "11px",
                            fontWeight: "500",
                            color: "#475569",
                            background: "#f1f5f9",
                            padding: "3px 8px",
                            borderRadius: "6px",
                          }}
                        >
                          <Icon size={12} />
                          {f.label}
                        </span>
                      );
                    })}
                  </div>

                  {/* Catered Domains */}
                  {lib.domains && lib.domains.length > 0 && (
                    <div>
                      <div style={{ fontSize: "11px", fontWeight: "600", color: "#94a3b8", textTransform: "uppercase", marginBottom: "4px" }}>
                        Aspirants Catered To:
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                        {lib.domains.slice(0, 4).map((d) => (
                          <span
                            key={d}
                            style={{
                              fontSize: "11px",
                              fontWeight: "600",
                              color: "#2563eb",
                              background: "#eff6ff",
                              border: "1px solid #dbeafe",
                              padding: "2px 7px",
                              borderRadius: "4px",
                            }}
                          >
                            {d}
                          </span>
                        ))}
                        {lib.domains.length > 4 && (
                          <span style={{ fontSize: "11px", color: "#64748b", padding: "2px" }}>
                            +{lib.domains.length - 4} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Card Action Footer */}
                <div style={{ padding: "16px 24px", borderTop: "1px solid #f1f5f9", background: "#fafafa" }}>
                  <Link
                    href={`/student/library/${lib.id}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px",
                      width: "100%",
                      padding: "10px 16px",
                      borderRadius: "8px",
                      background: "#2563eb",
                      color: "#ffffff",
                      fontWeight: "600",
                      fontSize: "14px",
                      textDecoration: "none",
                      boxShadow: "0 2px 4px rgba(37, 99, 235, 0.15)",
                    }}
                  >
                    <span>View Library & Live Seat Map</span>
                    <ArrowRight size={16} />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
