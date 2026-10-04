"use client";

import React, { useState, useEffect, use } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { authStorage } from "@/lib/auth";
import { Library, Seat, PricingPlan } from "@/lib/types";
import SeatGrid from "@/components/seat-map/SeatGrid";
import DomainChart from "@/components/charts/DomainChart";
import {
  ArrowLeft,
  MapPin,
  Clock,
  Phone,
  Mail,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Wifi,
  Wind,
  Zap,
  Coffee,
  BookOpen,
  Lock,
  DollarSign,
  Armchair,
  Sparkles,
  Info,
  Calendar,
} from "lucide-react";

export default function LibraryExplorePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const [library, setLibrary] = useState<Library | null>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Selected seat & shift state
  const [selectedSeat, setSelectedSeat] = useState<Seat | null>(null);
  const [activeShift, setActiveShift] = useState("full_day");
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [bookingModalOpen, setBookingModalOpen] = useState(false);

  useEffect(() => {
    fetchLibraryAndSeats();
  }, [id]);

  const fetchLibraryAndSeats = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [libData, seatList] = await Promise.all([
        apiClient.getLibrary(id),
        apiClient.getLibrarySeats(id),
      ]);
      setLibrary(libData);
      setSeats(seatList);

      // Select default plan if available
      if (libData.plans && libData.plans.length > 0 && libData.plans[0].id) {
        setSelectedPlanId(libData.plans[0].id);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load library details.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSeatSelection = (seat: Seat) => {
    setSelectedSeat(seat);
  };

  const handleProceedBooking = () => {
    setBookingModalOpen(true);
  };

  if (isLoading) {
    return (
      <div style={{ maxWidth: "1100px", margin: "40px auto", padding: "0 20px" }}>
        <div style={{ height: "300px", background: "#f1f5f9", borderRadius: "16px", marginBottom: "24px", animation: "pulse 1.5s infinite" }} />
        <div style={{ height: "400px", background: "#f1f5f9", borderRadius: "16px", animation: "pulse 1.5s infinite" }} />
      </div>
    );
  }

  if (errorMessage || !library) {
    return (
      <div style={{ maxWidth: "600px", margin: "60px auto", padding: "0 20px", textAlign: "center" }}>
        <div
          style={{
            background: "#fee2e2",
            border: "1px solid #fecaca",
            borderRadius: "16px",
            padding: "32px",
            color: "#991b1b",
          }}
        >
          <AlertCircle size={40} color="#dc2626" style={{ margin: "0 auto 12px" }} />
          <h2 style={{ fontSize: "20px", fontWeight: "700", marginBottom: "8px" }}>
            Library Not Found
          </h2>
          <p style={{ fontSize: "14px", marginBottom: "20px" }}>
            {errorMessage || "The requested library profile could not be loaded."}
          </p>
          <Link
            href="/student/discover"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              background: "#2563eb",
              color: "#ffffff",
              padding: "10px 20px",
              borderRadius: "8px",
              fontWeight: "600",
              textDecoration: "none",
            }}
          >
            <ArrowLeft size={16} />
            Back to Discover Libraries
          </Link>
        </div>
      </div>
    );
  }

  const emptySeats = library.seat_summary?.empty ?? seats.filter((s) => s.status === "empty").length;
  const totalSeats = library.seat_summary?.total ?? (seats.length > 0 ? seats.length : library.total_seats);
  const reservedSeats = library.seat_summary?.reserved ?? seats.filter((s) => s.status === "reserved").length;
  const occupiedSeats = library.seat_summary?.occupied ?? seats.filter((s) => s.status === "occupied").length;
  const occupancyPct = totalSeats > 0 ? Math.round(((totalSeats - emptySeats) / totalSeats) * 100) : 0;

  return (
    <div style={{ maxWidth: "1200px", margin: "24px auto", padding: "0 20px 60px" }}>
      {/* Back Link */}
      <div style={{ marginBottom: "20px" }}>
        <Link
          href="/student/discover"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            color: "#2563eb",
            fontWeight: "600",
            fontSize: "14px",
            textDecoration: "none",
          }}
        >
          <ArrowLeft size={16} />
          <span>Back to Discover Libraries</span>
        </Link>
      </div>

      {/* Library Hero Banner */}
      <div
        style={{
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
          borderRadius: "20px",
          padding: "36px 32px",
          color: "#ffffff",
          marginBottom: "32px",
          boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "20px" }}>
          <div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "rgba(59, 130, 246, 0.2)", border: "1px solid rgba(59, 130, 246, 0.3)", padding: "4px 12px", borderRadius: "16px", fontSize: "12px", fontWeight: "600", color: "#93c5fd", marginBottom: "12px" }}>
              <ShieldCheck size={14} />
              <span>Verified Study Facility</span>
            </div>
            <h1 style={{ fontSize: "32px", fontWeight: "800", marginBottom: "8px" }}>
              {library.name}
            </h1>
            <p style={{ fontSize: "15px", color: "#94a3b8", display: "flex", alignItems: "center", gap: "6px", marginBottom: "16px" }}>
              <MapPin size={16} color="#60a5fa" />
              {library.address}
            </p>

            <div style={{ display: "flex", flexWrap: "wrap", gap: "20px", fontSize: "14px", color: "#cbd5e1" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Clock size={16} color="#60a5fa" />
                <span>{library.operating_hours || "08:00 AM - 10:00 PM"}</span>
              </div>
              {library.contact_phone && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <Phone size={16} color="#60a5fa" />
                  <span>{library.contact_phone}</span>
                </div>
              )}
              {library.contact_email && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <Mail size={16} color="#60a5fa" />
                  <span>{library.contact_email}</span>
                </div>
              )}
            </div>
          </div>

          {/* Quick Availability Badge */}
          <div
            style={{
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: "16px",
              padding: "20px 24px",
              textAlign: "center",
              minWidth: "180px",
            }}
          >
            <div style={{ fontSize: "30px", fontWeight: "800", color: "#34d399", marginBottom: "2px" }}>
              {emptySeats}
            </div>
            <div style={{ fontSize: "13px", fontWeight: "600", color: "#e2e8f0" }}>
              Seats Available Now
            </div>
            <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
              out of {totalSeats} total desks
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Left Details & Right Seat Map */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "32px" }}>
        {/* Capacity Stat Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
          <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "18px 20px" }}>
            <div style={{ fontSize: "13px", fontWeight: "600", color: "#64748b", marginBottom: "4px" }}>Total Capacity</div>
            <div style={{ fontSize: "24px", fontWeight: "800", color: "#0f172a" }}>{totalSeats} Desks</div>
          </div>
          <div style={{ background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: "12px", padding: "18px 20px" }}>
            <div style={{ fontSize: "13px", fontWeight: "600", color: "#047857", marginBottom: "4px" }}>Available (Empty)</div>
            <div style={{ fontSize: "24px", fontWeight: "800", color: "#065f46" }}>{emptySeats} Seats</div>
          </div>
          <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: "12px", padding: "18px 20px" }}>
            <div style={{ fontSize: "13px", fontWeight: "600", color: "#b45309", marginBottom: "4px" }}>In-Progress Holds</div>
            <div style={{ fontSize: "24px", fontWeight: "800", color: "#92400e" }}>{reservedSeats} Reserved</div>
          </div>
          <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "12px", padding: "18px 20px" }}>
            <div style={{ fontSize: "13px", fontWeight: "600", color: "#b91c1c", marginBottom: "4px" }}>Occupied by Members</div>
            <div style={{ fontSize: "24px", fontWeight: "800", color: "#991b1b" }}>{occupiedSeats} Occupied</div>
          </div>
        </div>

        {/* Verified Amenities & Facilities */}
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "16px",
            padding: "24px",
          }}
        >
          <h3 style={{ fontSize: "17px", fontWeight: "700", color: "#0f172a", marginBottom: "16px" }}>
            Verified Facilities & Study Amenities
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
            {[
              { icon: Wifi, title: "High-Speed WiFi", desc: "Dual optical fiber 300 Mbps bandwidth" },
              { icon: Wind, title: "Centralized AC", desc: "Temperature-controlled quiet study zone" },
              { icon: Zap, title: "Power Socket on Desk", desc: "Dedicated individual plug for laptops & tablets" },
              { icon: Coffee, title: "RO Drinking Water", desc: "Cold and hot clean purified drinking water" },
              { icon: Armchair, title: "Ergonomic Chairs", desc: "Lumbar support designed for long sitting hours" },
              { icon: Lock, title: "Personal Lockers", desc: "Secure book & bag storage available" },
            ].map((amenity, idx) => {
              const Icon = amenity.icon;
              return (
                <div key={idx} style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <div
                    style={{
                      width: "36px",
                      height: "36px",
                      borderRadius: "8px",
                      background: "#eff6ff",
                      color: "#2563eb",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Icon size={18} />
                  </div>
                  <div>
                    <div style={{ fontSize: "14px", fontWeight: "700", color: "#1e293b" }}>{amenity.title}</div>
                    <div style={{ fontSize: "12px", color: "#64748b" }}>{amenity.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Pricing & Membership Plans */}
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "16px",
            padding: "24px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ fontSize: "17px", fontWeight: "700", color: "#0f172a" }}>
              Pricing Plans & Membership Options
            </h3>
            <span style={{ fontSize: "12px", color: "#059669", fontWeight: "600", background: "#ecfdf5", padding: "4px 10px", borderRadius: "12px" }}>
              No Hidden Charges
            </span>
          </div>

          {library.plans && library.plans.length > 0 ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "16px" }}>
              {library.plans.map((plan) => {
                const isSelected = selectedPlanId === plan.id;
                return (
                  <div
                    key={plan.id || plan.name}
                    onClick={() => plan.id && setSelectedPlanId(plan.id)}
                    style={{
                      border: `2px solid ${isSelected ? "#2563eb" : "#e2e8f0"}`,
                      background: isSelected ? "#eff6ff" : "#ffffff",
                      borderRadius: "12px",
                      padding: "20px",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                      position: "relative",
                    }}
                  >
                    {isSelected && (
                      <span
                        style={{
                          position: "absolute",
                          top: "10px",
                          right: "12px",
                          background: "#2563eb",
                          color: "#ffffff",
                          fontSize: "10px",
                          fontWeight: "700",
                          padding: "2px 8px",
                          borderRadius: "10px",
                        }}
                      >
                        Selected Plan
                      </span>
                    )}
                    <h4 style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a", marginBottom: "6px" }}>
                      {plan.name}
                    </h4>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "4px", marginBottom: "8px" }}>
                      <span style={{ fontSize: "26px", fontWeight: "800", color: "#2563eb" }}>₹{plan.price}</span>
                      <span style={{ fontSize: "13px", color: "#64748b" }}>/ {plan.duration_days} days</span>
                    </div>
                    <div style={{ fontSize: "12px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <Calendar size={13} />
                      <span>Valid for {plan.duration_days} calendar days</span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ fontSize: "14px", color: "#64748b" }}>
              No custom pricing plans configured yet. Standard rates apply.
            </p>
          )}
        </div>

        {/* Live Visual Seat Grid Component (FR-05) */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <h2 style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a" }}>
                Live Visual Seat Map
              </h2>
              <p style={{ fontSize: "13px", color: "#64748b" }}>
                Click on any green (Available) desk to inspect and reserve your dedicated position.
              </p>
            </div>
          </div>

          <SeatGrid
            seats={seats}
            selectedSeatId={selectedSeat?.id}
            onSelectSeat={handleSeatSelection}
            activeShift={activeShift}
            onShiftChange={(shift) => setActiveShift(shift)}
            interactive={true}
          />
        </div>

        {/* Floating/Bottom Selected Seat Reservation Drawer */}
        {selectedSeat && (
          <div
            style={{
              background: "#1e293b",
              color: "#ffffff",
              borderRadius: "16px",
              padding: "20px 24px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "16px",
              boxShadow: "0 10px 15px -3px rgba(0,0,0,0.2)",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <CheckCircle2 size={18} color="#34d399" />
                <span style={{ fontSize: "16px", fontWeight: "700" }}>
                  Selected Desk: {selectedSeat.label}
                </span>
                <span style={{ fontSize: "11px", background: "#059669", padding: "2px 8px", borderRadius: "10px", fontWeight: "600" }}>
                  Available
                </span>
              </div>
              <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                Shift: {activeShift.replace("_", " ").toUpperCase()} • {library.name}
              </p>
            </div>

            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <button
                type="button"
                onClick={() => setSelectedSeat(null)}
                style={{
                  background: "transparent",
                  border: "1px solid #475569",
                  color: "#cbd5e1",
                  padding: "9px 16px",
                  borderRadius: "8px",
                  fontWeight: "600",
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                Clear Selection
              </button>
              <button
                type="button"
                onClick={handleProceedBooking}
                style={{
                  background: "#2563eb",
                  color: "#ffffff",
                  padding: "10px 24px",
                  borderRadius: "8px",
                  border: "none",
                  fontWeight: "700",
                  fontSize: "14px",
                  cursor: "pointer",
                  boxShadow: "0 2px 4px rgba(37, 99, 235, 0.3)",
                }}
              >
                Reserve This Seat →
              </button>
            </div>
          </div>
        )}

        {/* Peer Aspirant Domain Breakdown */}
        <DomainChart
          domains={library.domains}
          breakdown={library.domain_breakdown}
          totalCount={totalSeats - emptySeats}
        />

        {/* Study Hall Etiquette Rules */}
        <div
          style={{
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "16px",
            padding: "24px",
            color: "#475569",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
            <Info size={18} color="#2563eb" />
            <h4 style={{ fontSize: "15px", fontWeight: "700", color: "#1e293b" }}>
              Study Hall Etiquette & Guidelines
            </h4>
          </div>
          <ul style={{ fontSize: "13px", lineHeight: "1.7", paddingLeft: "20px" }}>
            <li>Maintain absolute silence in reading rooms. Please take phone calls in the reception or lobby area.</li>
            <li>Keep personal desk areas neat and clean. Trash bins are located at each aisle.</li>
            <li>Seat reservations are verified via your digital student membership badge upon entry.</li>
          </ul>
        </div>
      </div>

      {/* Booking / Reservation Info Modal */}
      {bookingModalOpen && selectedSeat && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: "20px",
              padding: "32px",
              maxWidth: "500px",
              width: "100%",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.2)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
              <div style={{ width: "36px", height: "36px", borderRadius: "50%", background: "#eff6ff", color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Sparkles size={20} />
              </div>
              <h3 style={{ fontSize: "20px", fontWeight: "700", color: "#0f172a" }}>
                Reserve Seat {selectedSeat.label}
              </h3>
            </div>

            <div style={{ background: "#f8fafc", borderRadius: "12px", padding: "16px", marginBottom: "20px", fontSize: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#64748b" }}>Library:</span>
                <span style={{ fontWeight: "600", color: "#1e293b" }}>{library.name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#64748b" }}>Desk Position:</span>
                <span style={{ fontWeight: "700", color: "#2563eb" }}>{selectedSeat.label}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#64748b" }}>Shift:</span>
                <span style={{ fontWeight: "600", color: "#1e293b" }}>{activeShift.replace("_", " ").toUpperCase()}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#64748b" }}>Status:</span>
                <span style={{ fontWeight: "700", color: "#059669" }}>Available for Immediate Hold</span>
              </div>
            </div>

            <p style={{ fontSize: "14px", color: "#475569", lineHeight: "1.5", marginBottom: "24px" }}>
              To complete the booking and pay via online payment gateway (UPI/Cards), you can proceed to the membership registration flow.
            </p>

            <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setBookingModalOpen(false)}
                style={{
                  padding: "10px 18px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  background: "#ffffff",
                  color: "#475569",
                  fontWeight: "600",
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => {
                  alert(`Seat ${selectedSeat.label} selected! Membership and payment flow will be finalized.`);
                  setBookingModalOpen(false);
                }}
                style={{
                  padding: "10px 20px",
                  borderRadius: "8px",
                  border: "none",
                  background: "#2563eb",
                  color: "#ffffff",
                  fontWeight: "600",
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                Confirm & Proceed
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
