"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { authStorage } from "@/lib/auth";
import {
  Library,
  PricingPlan,
  Seat,
  SeatStatus,
  LibraryCreateInput,
} from "@/lib/types";
import {
  Building2,
  MapPin,
  Clock,
  BookOpen,
  DollarSign,
  Grid,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  Save,
  RotateCcw,
  Sparkles,
  Lock,
} from "lucide-react";

const POPULAR_DOMAINS = [
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

const DEFAULT_PLANS: Array<{ name: string; duration_days: number; price: number }> = [
  { name: "Monthly Standard", duration_days: 30, price: 1200 },
  { name: "Quarterly Saver", duration_days: 90, price: 3200 },
  { name: "Half-Yearly Pass", duration_days: 180, price: 6000 },
];

export default function OwnerSetupPage() {
  // Mode & Loading states
  const [isEditing, setIsEditing] = useState(false);
  const [existingLibraryId, setExistingLibraryId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authEmail, setAuthEmail] = useState("owner@example.com");
  const [authPassword, setAuthPassword] = useState("password123");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Step navigation
  const [activeStep, setActiveStep] = useState<number>(1);

  // Form State: 1. Basic & Location
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [latitude, setLatitude] = useState<string>("28.6139");
  const [longitude, setLongitude] = useState<string>("77.2090");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  // Form State: 2. Hours & Domains
  const [opensAt, setOpensAt] = useState("08:00");
  const [closesAt, setClosesAt] = useState("22:00");
  const [operatingHoursNotes, setOperatingHoursNotes] = useState("Open 7 days a week, 8:00 AM to 10:00 PM");
  const [selectedDomains, setSelectedDomains] = useState<string[]>(["UPSC", "SSC"]);
  const [customDomainInput, setCustomDomainInput] = useState("");

  // Form State: 3. Pricing Plans
  const [pricingPlans, setPricingPlans] = useState<Array<{ name: string; duration_days: number; price: number }>>(DEFAULT_PLANS);
  const [newPlanName, setNewPlanName] = useState("");
  const [newPlanDays, setNewPlanDays] = useState(30);
  const [newPlanPrice, setNewPlanPrice] = useState(1000);

  // Form State: 4. Initial Seat Layout
  const [gridRows, setGridRows] = useState<string>("A, B, C");
  const [gridSeatsPerRow, setGridSeatsPerRow] = useState<number>(5);
  const [seats, setSeats] = useState<Array<{ label: string; status: SeatStatus }>>([]);
  const [newSeatLabel, setNewSeatLabel] = useState("");

  // Check auth and fetch existing library
  useEffect(() => {
    checkAuthAndLoad();
  }, []);

  const checkAuthAndLoad = async () => {
    setIsLoading(true);
    setFeedback(null);
    const token = authStorage.getAccessToken();
    if (!token) {
      setIsAuthenticated(false);
      setIsLoading(false);
      return;
    }

    setIsAuthenticated(true);
    try {
      const myLib = await apiClient.getMyLibrary();
      if (myLib && myLib.id) {
        setIsEditing(true);
        setExistingLibraryId(myLib.id);
        populateExistingLibrary(myLib);
      }
    } catch (err: any) {
      // 404 is expected for fresh owners who haven't completed setup yet
      if (err.status !== 404) {
        setFeedback({ type: "error", message: err.message || "Failed to fetch library" });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const populateExistingLibrary = async (lib: Library) => {
    setName(lib.name || "");
    setAddress(lib.address || "");
    setLatitude(String(lib.latitude ?? "28.6139"));
    setLongitude(String(lib.longitude ?? "77.2090"));
    setContactPhone(lib.contact_phone || "");
    setContactEmail(lib.contact_email || "");
    setOpensAt(lib.opens_at ? lib.opens_at.slice(0, 5) : "08:00");
    setClosesAt(lib.closes_at ? lib.closes_at.slice(0, 5) : "22:00");
    setOperatingHoursNotes(lib.operating_hours || "");

    if (lib.domains && lib.domains.length > 0) {
      setSelectedDomains(lib.domains);
    } else if (lib.domains_catered) {
      setSelectedDomains(lib.domains_catered.split(",").map((s) => s.trim()));
    }

    if (lib.plans && lib.plans.length > 0) {
      setPricingPlans(
        lib.plans.map((p) => ({
          name: p.name,
          duration_days: p.duration_days,
          price: Number(p.price),
        }))
      );
    }

    // Load existing seats
    try {
      const existingSeats = await apiClient.getLibrarySeats(lib.id);
      if (existingSeats && existingSeats.length > 0) {
        setSeats(
          existingSeats.map((s) => ({
            label: s.label,
            status: s.status,
          }))
        );
      }
    } catch (e) {
      console.warn("Could not load seats for library", e);
    }
  };

  // Quick Login / Auth Modal Handler
  const handleQuickLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoggingIn(true);
    setFeedback(null);
    try {
      await apiClient.login({ email: authEmail, password: authPassword });
      setIsAuthenticated(true);
      setFeedback({ type: "success", message: "Logged in successfully as Owner!" });
      await checkAuthAndLoad();
    } catch (err: any) {
      setFeedback({ type: "error", message: err.message || "Login failed. Please check credentials." });
    } finally {
      setIsLoggingIn(false);
    }
  };

  // Domain toggling
  const toggleDomain = (domain: string) => {
    if (selectedDomains.includes(domain)) {
      setSelectedDomains(selectedDomains.filter((d) => d !== domain));
    } else {
      setSelectedDomains([...selectedDomains, domain]);
    }
  };

  const addCustomDomain = () => {
    const trimmed = customDomainInput.trim();
    if (trimmed && !selectedDomains.includes(trimmed)) {
      setSelectedDomains([...selectedDomains, trimmed]);
      setCustomDomainInput("");
    }
  };

  // Pricing Plan management
  const addPricingPlan = () => {
    if (!newPlanName.trim()) return;
    setPricingPlans([
      ...pricingPlans,
      {
        name: newPlanName.trim(),
        duration_days: Number(newPlanDays) || 30,
        price: Number(newPlanPrice) || 0,
      },
    ]);
    setNewPlanName("");
    setNewPlanDays(30);
    setNewPlanPrice(1000);
  };

  const removePricingPlan = (index: number) => {
    setPricingPlans(pricingPlans.filter((_, i) => i !== index));
  };

  // Seat Generation
  const generateSeatsFromGrid = () => {
    const rowList = gridRows
      .split(",")
      .map((r) => r.trim().toUpperCase())
      .filter((r) => r.length > 0);

    const generated: Array<{ label: string; status: SeatStatus }> = [];
    rowList.forEach((row) => {
      for (let s = 1; s <= gridSeatsPerRow; s++) {
        generated.push({
          label: `Row ${row} - Seat ${s}`,
          status: "empty",
        });
      }
    });

    setSeats(generated);
    setFeedback({
      type: "success",
      message: `Generated ${generated.length} seats (${rowList.length} rows × ${gridSeatsPerRow} seats/row).`,
    });
  };

  const addSingleSeat = () => {
    if (!newSeatLabel.trim()) return;
    const trimmed = newSeatLabel.trim();
    if (seats.some((s) => s.label.toLowerCase() === trimmed.toLowerCase())) {
      setFeedback({ type: "error", message: `Seat "${trimmed}" already exists.` });
      return;
    }
    setSeats([...seats, { label: trimmed, status: "empty" }]);
    setNewSeatLabel("");
  };

  const removeSeat = (index: number) => {
    setSeats(seats.filter((_, i) => i !== index));
  };

  const cycleSeatStatus = (index: number) => {
    const seat = seats[index];
    const nextStatus: Record<SeatStatus, SeatStatus> = {
      empty: "reserved",
      reserved: "occupied",
      occupied: "empty",
    };
    const updated = [...seats];
    updated[index] = { ...seat, status: nextStatus[seat.status] };
    setSeats(updated);
  };

  // Submit / Save Setup
  const handleSubmit = async () => {
    if (!name.trim()) {
      setFeedback({ type: "error", message: "Library name is required." });
      setActiveStep(1);
      return;
    }
    if (!address.trim()) {
      setFeedback({ type: "error", message: "Library address is required." });
      setActiveStep(1);
      return;
    }

    setIsSaving(true);
    setFeedback(null);

    const payload: LibraryCreateInput = {
      name: name.trim(),
      address: address.trim(),
      latitude: parseFloat(latitude) || 0.0,
      longitude: parseFloat(longitude) || 0.0,
      contact_phone: contactPhone.trim() || undefined,
      contact_email: contactEmail.trim() || undefined,
      total_seats: seats.length,
      opens_at: opensAt ? `${opensAt}:00` : undefined,
      closes_at: closesAt ? `${closesAt}:00` : undefined,
      operating_hours: operatingHoursNotes.trim() || undefined,
      domains_catered: selectedDomains.join(","),
      pricing_plans: pricingPlans,
      initial_seats: seats,
    };

    try {
      if (isEditing && existingLibraryId) {
        const updated = await apiClient.updateLibrary(existingLibraryId, payload);
        // Also ensure seats are updated/synced
        if (seats.length > 0) {
          await apiClient.addLibrarySeats(existingLibraryId, seats);
        }
        setFeedback({
          type: "success",
          message: `Library "${updated.name}" updated successfully!`,
        });
      } else {
        const created = await apiClient.createLibrary(payload);
        setIsEditing(true);
        setExistingLibraryId(created.id);
        setFeedback({
          type: "success",
          message: `Library "${created.name}" created successfully with ${created.total_seats} seats!`,
        });
      }
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to save library profile. Please check all fields.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: "1000px", margin: "32px auto", padding: "0 20px" }}>
      {/* Auth Banner if not authenticated */}
      {!isAuthenticated && !isLoading && (
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: "12px",
            padding: "24px",
            marginBottom: "28px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
            <Lock size={20} color="#2563eb" />
            <h3 style={{ fontSize: "17px", fontWeight: "600", color: "#1e40af" }}>
              Owner Authentication Required
            </h3>
          </div>
          <p style={{ fontSize: "14px", color: "#1e3a8a", marginBottom: "16px" }}>
            Please authenticate with your Library Owner credentials to proceed with onboarding or editing your library.
          </p>
          <form onSubmit={handleQuickLogin} style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <input
              type="email"
              value={authEmail}
              onChange={(e) => setAuthEmail(e.target.value)}
              placeholder="Owner Email"
              required
              style={{
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid #93c5fd",
                minWidth: "220px",
              }}
            />
            <input
              type="password"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              placeholder="Password"
              required
              style={{
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid #93c5fd",
                minWidth: "160px",
              }}
            />
            <button
              type="submit"
              disabled={isLoggingIn}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                padding: "8px 18px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
              }}
            >
              {isLoggingIn ? "Logging in..." : "Login as Owner"}
            </button>
          </form>
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "6px" }}>
            <h1 style={{ fontSize: "28px", fontWeight: "800", color: "#0f172a" }}>
              {isEditing ? "Edit Library Profile" : "Library Setup & Onboarding"}
            </h1>
            <span
              style={{
                fontSize: "12px",
                fontWeight: "600",
                padding: "4px 10px",
                borderRadius: "16px",
                background: isEditing ? "#dcfce7" : "#dbeafe",
                color: isEditing ? "#15803d" : "#1d4ed8",
              }}
            >
              {isEditing ? "Profile Configured" : "Step 1: Fresh Onboarding"}
            </span>
          </div>
          <p style={{ fontSize: "15px", color: "#64748b" }}>
            {isEditing
              ? "Update your library details, pricing plans, and seat configuration."
              : "Complete your one-time onboarding by setting up your library details, operational hours, plans, and seat layout."}
          </p>
        </div>

        <button
          onClick={handleSubmit}
          disabled={isSaving}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background: "#2563eb",
            color: "#ffffff",
            padding: "10px 22px",
            borderRadius: "8px",
            border: "none",
            fontWeight: "600",
            fontSize: "15px",
            boxShadow: "0 2px 4px rgba(37, 99, 235, 0.2)",
          }}
        >
          <Save size={18} />
          {isSaving ? "Saving..." : isEditing ? "Save Changes" : "Complete Setup"}
        </button>
      </div>

      {/* Feedback Alert */}
      {feedback && (
        <div
          style={{
            padding: "14px 18px",
            borderRadius: "8px",
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            background: feedback.type === "success" ? "#dcfce7" : "#fee2e2",
            border: `1px solid ${feedback.type === "success" ? "#bbf7d0" : "#fecaca"}`,
            color: feedback.type === "success" ? "#166534" : "#991b1b",
          }}
        >
          {feedback.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span style={{ fontSize: "14px", fontWeight: "500" }}>{feedback.message}</span>
        </div>
      )}

      {/* Step Indicators */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "12px",
          marginBottom: "28px",
        }}
      >
        {[
          { num: 1, title: "Basic & Location", icon: Building2 },
          { num: 2, title: "Hours & Domains", icon: Clock },
          { num: 3, title: "Pricing Plans", icon: DollarSign },
          { num: 4, title: "Seat Layout", icon: Grid },
        ].map((step) => {
          const Icon = step.icon;
          const isActive = activeStep === step.num;
          return (
            <button
              key={step.num}
              onClick={() => setActiveStep(step.num)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "12px 14px",
                borderRadius: "10px",
                border: `1px solid ${isActive ? "#2563eb" : "#e2e8f0"}`,
                background: isActive ? "#eff6ff" : "#ffffff",
                color: isActive ? "#1d4ed8" : "#475569",
                fontWeight: isActive ? "600" : "500",
                fontSize: "14px",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
            >
              <div
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  background: isActive ? "#2563eb" : "#f1f5f9",
                  color: isActive ? "#ffffff" : "#64748b",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "13px",
                  fontWeight: "700",
                }}
              >
                {step.num}
              </div>
              <span>{step.title}</span>
            </button>
          );
        })}
      </div>

      {/* STEP 1: Basic & Location */}
      {activeStep === 1 && (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "28px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", borderBottom: "1px solid #f1f5f9", paddingBottom: "14px" }}>
            <Building2 size={22} color="#2563eb" />
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a" }}>
              Library Basic Information & Contact
            </h2>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
              Library Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Apex Reading Lounge & Library"
              required
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
                fontSize: "15px",
              }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
              Full Address *
            </label>
            <textarea
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="e.g. 4th Floor, City Hub Complex, Sector 62, Noida, Uttar Pradesh"
              rows={2}
              required
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
                fontSize: "15px",
              }}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
                Contact Phone
              </label>
              <input
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="+91 9876543210"
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "15px",
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
                Contact Email
              </label>
              <input
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="contact@apexlibrary.com"
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "15px",
                }}
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
                Latitude (GPS)
              </label>
              <input
                type="text"
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                placeholder="28.6139"
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "15px",
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
                Longitude (GPS)
              </label>
              <input
                type="text"
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                placeholder="77.2090"
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "15px",
                }}
              />
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "12px" }}>
            <button
              type="button"
              onClick={() => setActiveStep(2)}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                padding: "9px 20px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
              }}
            >
              Next: Hours & Domains →
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: Operating Hours & Domains */}
      {activeStep === 2 && (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "28px",
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", borderBottom: "1px solid #f1f5f9", paddingBottom: "14px" }}>
            <Clock size={22} color="#2563eb" />
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a" }}>
              Operating Hours & Competitive Exam Domains
            </h2>
          </div>

          {/* Timings */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
                Opens At
              </label>
              <input
                type="time"
                value={opensAt}
                onChange={(e) => setOpensAt(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "15px",
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
                Closes At
              </label>
              <input
                type="time"
                value={closesAt}
                onChange={(e) => setClosesAt(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "15px",
                }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
              Operating Hours Note
            </label>
            <input
              type="text"
              value={operatingHoursNotes}
              onChange={(e) => setOperatingHoursNotes(e.target.value)}
              placeholder="e.g. Open 7 days a week, 24 Hours on Exam Months"
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
                fontSize: "15px",
              }}
            />
          </div>

          {/* Domains Catered */}
          <div>
            <label style={{ display: "block", fontSize: "14px", fontWeight: "600", marginBottom: "6px" }}>
              Domains Catered To (Students can filter and discover by domain)
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "14px" }}>
              {POPULAR_DOMAINS.map((domain) => {
                const isSelected = selectedDomains.includes(domain);
                return (
                  <button
                    key={domain}
                    type="button"
                    onClick={() => toggleDomain(domain)}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "20px",
                      fontSize: "13px",
                      fontWeight: "600",
                      border: `1px solid ${isSelected ? "#2563eb" : "#cbd5e1"}`,
                      background: isSelected ? "#eff6ff" : "#ffffff",
                      color: isSelected ? "#2563eb" : "#475569",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {isSelected ? "✓ " : "+ "}
                    {domain}
                  </button>
                );
              })}
            </div>

            <div style={{ display: "flex", gap: "10px" }}>
              <input
                type="text"
                value={customDomainInput}
                onChange={(e) => setCustomDomainInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCustomDomain();
                  }
                }}
                placeholder="Add custom domain (e.g. Judiciary, CDS)..."
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "14px",
                }}
              />
              <button
                type="button"
                onClick={addCustomDomain}
                style={{
                  background: "#475569",
                  color: "#ffffff",
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "none",
                  fontWeight: "600",
                  fontSize: "14px",
                }}
              >
                Add Domain
              </button>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "12px" }}>
            <button
              type="button"
              onClick={() => setActiveStep(1)}
              style={{
                background: "#f1f5f9",
                color: "#475569",
                padding: "9px 18px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
              }}
            >
              ← Back
            </button>
            <button
              type="button"
              onClick={() => setActiveStep(3)}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                padding: "9px 20px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
              }}
            >
              Next: Pricing Plans →
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Pricing Plans */}
      {activeStep === 3 && (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "28px",
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", borderBottom: "1px solid #f1f5f9", paddingBottom: "14px" }}>
            <DollarSign size={22} color="#2563eb" />
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a" }}>
              Configure Membership Pricing Plans
            </h2>
          </div>

          <p style={{ fontSize: "14px", color: "#64748b" }}>
            Set up the subscription tiers available to students for reserving seats in your library.
          </p>

          {/* Existing Plans List */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "14px" }}>
            {pricingPlans.map((plan, index) => (
              <div
                key={index}
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "10px",
                  padding: "16px",
                  position: "relative",
                }}
              >
                <button
                  type="button"
                  onClick={() => removePricingPlan(index)}
                  style={{
                    position: "absolute",
                    top: "12px",
                    right: "12px",
                    background: "none",
                    border: "none",
                    color: "#94a3b8",
                    padding: "4px",
                  }}
                  title="Remove Plan"
                >
                  <Trash2 size={16} />
                </button>
                <div style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a", marginBottom: "4px" }}>
                  {plan.name}
                </div>
                <div style={{ fontSize: "13px", color: "#64748b", marginBottom: "12px" }}>
                  Duration: {plan.duration_days} Days
                </div>
                <div style={{ fontSize: "22px", fontWeight: "800", color: "#2563eb" }}>
                  ₹{plan.price}
                </div>
              </div>
            ))}
          </div>

          {/* Add New Plan */}
          <div
            style={{
              background: "#f1f5f9",
              borderRadius: "10px",
              padding: "18px",
              marginTop: "10px",
            }}
          >
            <div style={{ fontSize: "14px", fontWeight: "700", marginBottom: "12px", color: "#334155" }}>
              + Add Custom Pricing Plan
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: "10px", alignItems: "flex-end" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", marginBottom: "4px" }}>
                  Plan Name
                </label>
                <input
                  type="text"
                  value={newPlanName}
                  onChange={(e) => setNewPlanName(e.target.value)}
                  placeholder="e.g. Yearly Pro"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "14px",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", marginBottom: "4px" }}>
                  Days
                </label>
                <input
                  type="number"
                  value={newPlanDays}
                  onChange={(e) => setNewPlanDays(Number(e.target.value))}
                  min={1}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "14px",
                  }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", marginBottom: "4px" }}>
                  Price (₹)
                </label>
                <input
                  type="number"
                  value={newPlanPrice}
                  onChange={(e) => setNewPlanPrice(Number(e.target.value))}
                  min={0}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "14px",
                  }}
                />
              </div>
              <button
                type="button"
                onClick={addPricingPlan}
                style={{
                  background: "#2563eb",
                  color: "#ffffff",
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "none",
                  fontWeight: "600",
                  fontSize: "14px",
                  height: "38px",
                }}
              >
                Add Plan
              </button>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "12px" }}>
            <button
              type="button"
              onClick={() => setActiveStep(2)}
              style={{
                background: "#f1f5f9",
                color: "#475569",
                padding: "9px 18px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
              }}
            >
              ← Back
            </button>
            <button
              type="button"
              onClick={() => setActiveStep(4)}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                padding: "9px 20px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
              }}
            >
              Next: Seat Layout Setup →
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: Initial Seat Layout */}
      {activeStep === 4 && (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "28px",
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", borderBottom: "1px solid #f1f5f9", paddingBottom: "14px" }}>
            <Grid size={22} color="#2563eb" />
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#0f172a" }}>
              Initial Seat Layout Configuration (FR-02)
            </h2>
          </div>

          <p style={{ fontSize: "14px", color: "#64748b" }}>
            Generate rows and seats for your library. Positional labels (e.g. <code>Row A - Seat 1</code>) allow students to easily locate their study desk.
          </p>

          {/* Quick Grid Generator */}
          <div
            style={{
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: "10px",
              padding: "18px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
              <Sparkles size={16} color="#2563eb" />
              <span style={{ fontSize: "14px", fontWeight: "700", color: "#1e293b" }}>
                Automatic Seat Grid Generator
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: "12px", alignItems: "flex-end" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", marginBottom: "4px" }}>
                  Row Letters / Names (comma-separated)
                </label>
                <input
                  type="text"
                  value={gridRows}
                  onChange={(e) => setGridRows(e.target.value)}
                  placeholder="e.g. A, B, C, D"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "14px",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", marginBottom: "4px" }}>
                  Seats per Row
                </label>
                <input
                  type="number"
                  value={gridSeatsPerRow}
                  onChange={(e) => setGridSeatsPerRow(Number(e.target.value))}
                  min={1}
                  max={50}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "14px",
                  }}
                />
              </div>

              <button
                type="button"
                onClick={generateSeatsFromGrid}
                style={{
                  background: "#2563eb",
                  color: "#ffffff",
                  padding: "8px 18px",
                  borderRadius: "6px",
                  border: "none",
                  fontWeight: "600",
                  fontSize: "14px",
                  height: "38px",
                }}
              >
                Generate Grid
              </button>
            </div>
          </div>

          {/* Add Single Seat */}
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <input
              type="text"
              value={newSeatLabel}
              onChange={(e) => setNewSeatLabel(e.target.value)}
              placeholder="Or add single seat (e.g. Quiet Corner - Seat 1)..."
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                fontSize: "14px",
              }}
            />
            <button
              type="button"
              onClick={addSingleSeat}
              style={{
                background: "#475569",
                color: "#ffffff",
                padding: "8px 16px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
                fontSize: "14px",
              }}
            >
              + Add Seat
            </button>
          </div>

          {/* Seat Map Summary & Interactive Grid Preview */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <div style={{ fontSize: "15px", fontWeight: "700", color: "#0f172a" }}>
                Seat Map Preview ({seats.length} Total Seats)
              </div>
              <div style={{ display: "flex", gap: "12px", fontSize: "12px" }}>
                <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#22c55e" }} />
                  Empty ({seats.filter((s) => s.status === "empty").length})
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#f59e0b" }} />
                  Reserved ({seats.filter((s) => s.status === "reserved").length})
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ef4444" }} />
                  Occupied ({seats.filter((s) => s.status === "occupied").length})
                </span>
              </div>
            </div>

            <p style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "12px" }}>
              💡 Tip: Click on any seat card to toggle its status (Empty → Reserved → Occupied).
            </p>

            {seats.length === 0 ? (
              <div
                style={{
                  padding: "36px",
                  textAlign: "center",
                  background: "#f8fafc",
                  borderRadius: "10px",
                  border: "1px dashed #cbd5e1",
                  color: "#94a3b8",
                }}
              >
                No seats generated yet. Use the grid generator above or add individual seats.
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
                  gap: "10px",
                  maxHeight: "360px",
                  overflowY: "auto",
                  padding: "4px",
                }}
              >
                {seats.map((seat, index) => {
                  const statusColors: Record<SeatStatus, { bg: string; border: string; text: string }> = {
                    empty: { bg: "#f0fdf4", border: "#bbf7d0", text: "#166534" },
                    reserved: { bg: "#fefce8", border: "#fef08a", text: "#854d0e" },
                    occupied: { bg: "#fef2f2", border: "#fecaca", text: "#991b1b" },
                  };
                  const colors = statusColors[seat.status];

                  return (
                    <div
                      key={index}
                      onClick={() => cycleSeatStatus(index)}
                      style={{
                        background: colors.bg,
                        border: `1px solid ${colors.border}`,
                        borderRadius: "8px",
                        padding: "10px",
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        textAlign: "center",
                        position: "relative",
                        userSelect: "none",
                        transition: "all 0.1s ease",
                      }}
                      title="Click to toggle status"
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeSeat(index);
                        }}
                        style={{
                          position: "absolute",
                          top: "4px",
                          right: "4px",
                          background: "none",
                          border: "none",
                          color: "#94a3b8",
                          padding: "2px",
                        }}
                        title="Delete Seat"
                      >
                        <Trash2 size={12} />
                      </button>

                      <div style={{ fontSize: "12px", fontWeight: "700", color: "#1e293b", marginBottom: "4px" }}>
                        {seat.label}
                      </div>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: "600",
                          textTransform: "uppercase",
                          color: colors.text,
                        }}
                      >
                        {seat.status}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "12px" }}>
            <button
              type="button"
              onClick={() => setActiveStep(3)}
              style={{
                background: "#f1f5f9",
                color: "#475569",
                padding: "9px 18px",
                borderRadius: "6px",
                border: "none",
                fontWeight: "600",
              }}
            >
              ← Back
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSaving}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                padding: "10px 24px",
                borderRadius: "8px",
                border: "none",
                fontWeight: "700",
                fontSize: "15px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Save size={18} />
              {isSaving ? "Saving..." : isEditing ? "Save & Update Profile" : "Save & Complete Setup"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
