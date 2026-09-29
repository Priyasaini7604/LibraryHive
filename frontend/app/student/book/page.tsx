"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { authStorage } from "@/lib/auth";
import {
  Library,
  Seat,
  PricingPlan,
  User,
} from "@/lib/types";
import {
  Building2,
  Armchair,
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Lock,
  ArrowRight,
  Loader2,
} from "lucide-react";

export default function StudentBookingPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [selectedLibrary, setSelectedLibrary] = useState<Library | null>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selectedSeat, setSelectedSeat] = useState<Seat | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PricingPlan | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingSeats, setIsLoadingSeats] = useState(false);
  const [isBooking, setIsBooking] = useState(false);

  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setIsLoading(true);
    setFeedback(null);

    const token = authStorage.getAccessToken();

    if (!token) {
      setFeedback({
        type: "error",
        message: "Please login as a student before booking a seat.",
      });
      setIsLoading(false);
      return;
    }

    try {
      const currentUser = authStorage.getUser();

      if (currentUser) {
        setUser(currentUser);
      } else {
        const fetchedUser = await apiClient.getMe();
        setUser(fetchedUser);
        authStorage.setUser(fetchedUser);
      }

      const libraryList = await apiClient.getLibraries();
      setLibraries(libraryList);
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to load libraries.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLibrarySelect = async (library: Library) => {
    setSelectedLibrary(library);
    setSelectedSeat(null);
    setSelectedPlan(null);
    setFeedback(null);

    setIsLoadingSeats(true);

    try {
      const librarySeats = await apiClient.getLibrarySeats(library.id);
      setSeats(librarySeats);

      if (!librarySeats.length) {
        setFeedback({
          type: "error",
          message: "No seats are configured for this library.",
        });
      }
    } catch (err: any) {
      setSeats([]);
      setFeedback({
        type: "error",
        message: err.message || "Failed to load seats.",
      });
    } finally {
      setIsLoadingSeats(false);
    }
  };

  const handleSeatSelect = (seat: Seat) => {
    if (seat.status !== "empty") {
      return;
    }

    setSelectedSeat(seat);
    setFeedback(null);
  };

  const handlePlanSelect = (plan: PricingPlan) => {
    setSelectedPlan(plan);
    setFeedback(null);
  };

  const handleBooking = async () => {
    if (!selectedLibrary) {
      setFeedback({
        type: "error",
        message: "Please select a library.",
      });
      return;
    }

    if (!selectedSeat) {
      setFeedback({
        type: "error",
        message: "Please select an available seat.",
      });
      return;
    }

    if (!selectedPlan?.id) {
      setFeedback({
        type: "error",
        message: "Please select a membership plan.",
      });
      return;
    }

    setIsBooking(true);
    setFeedback(null);

    try {
      const booking = await apiClient.createBooking({
        library: selectedLibrary.id,
        seat: selectedSeat.id,
        plan: selectedPlan.id,
      });

      setFeedback({
        type: "success",
        message:
          "Seat reserved successfully. Continue to payment before the reservation expires.",
      });

      // Store the booking temporarily so the payment page can use it.
      sessionStorage.setItem(
        "libraryhive_pending_booking",
        JSON.stringify(booking)
      );

      // Move to payment page.
      router.push("/student/payment");
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to reserve the seat.",
      });
    } finally {
      setIsBooking(false);
    }
  };

  const availableSeats = seats.filter(
    (seat) => seat.status === "empty"
  );

  const getPlanPrice = (plan: PricingPlan) => {
    const price = Number(plan.price);

    if (Number.isNaN(price)) {
      return "0";
    }

    return price.toLocaleString("en-IN");
  };

  if (isLoading) {
    return (
      <div
        style={{
          maxWidth: "1000px",
          margin: "60px auto",
          padding: "0 20px",
          textAlign: "center",
        }}
      >
        <Loader2
          size={32}
          color="#2563eb"
          style={{ animation: "spin 1s linear infinite" }}
        />
        <p
          style={{
            marginTop: "12px",
            color: "#64748b",
            fontSize: "14px",
          }}
        >
          Loading libraries...
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        maxWidth: "1100px",
        margin: "32px auto",
        padding: "0 20px 40px",
      }}
    >
      {/* Header */}
      <div
        style={{
          marginBottom: "24px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "6px",
          }}
        >
          <h1
            style={{
              fontSize: "28px",
              fontWeight: "800",
              color: "#0f172a",
              margin: 0,
            }}
          >
            Book Your Study Seat
          </h1>

          <span
            style={{
              fontSize: "12px",
              fontWeight: "600",
              padding: "4px 10px",
              borderRadius: "16px",
              background: "#dbeafe",
              color: "#1d4ed8",
            }}
          >
            Student
          </span>
        </div>

        <p
          style={{
            fontSize: "15px",
            color: "#64748b",
            margin: 0,
          }}
        >
          Choose a library, select an available seat and membership plan.
        </p>
      </div>

      {/* Student information */}
      {user && (
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: "10px",
            padding: "14px 18px",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              fontSize: "13px",
              color: "#1e40af",
              fontWeight: "600",
            }}
          >
            Booking as
          </div>

          <div
            style={{
              fontSize: "15px",
              color: "#1e3a8a",
              marginTop: "3px",
            }}
          >
            {user.name} — {user.email}
          </div>
        </div>
      )}

      {/* Feedback */}
      {feedback && (
        <div
          style={{
            padding: "14px 18px",
            borderRadius: "8px",
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            background:
              feedback.type === "success" ? "#dcfce7" : "#fee2e2",
            border:
              feedback.type === "success"
                ? "1px solid #bbf7d0"
                : "1px solid #fecaca",
            color:
              feedback.type === "success" ? "#166534" : "#991b1b",
          }}
        >
          {feedback.type === "success" ? (
            <CheckCircle2 size={18} />
          ) : (
            <AlertCircle size={18} />
          )}

          <span
            style={{
              fontSize: "14px",
              fontWeight: "500",
            }}
          >
            {feedback.message}
          </span>
        </div>
      )}

      {/* STEP 1 — Library */}
      <section
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "12px",
          padding: "24px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            borderBottom: "1px solid #f1f5f9",
            paddingBottom: "14px",
            marginBottom: "18px",
          }}
        >
          <Building2 size={22} color="#2563eb" />

          <div>
            <h2
              style={{
                fontSize: "18px",
                fontWeight: "700",
                color: "#0f172a",
                margin: 0,
              }}
            >
              1. Select Library
            </h2>

            <p
              style={{
                fontSize: "13px",
                color: "#64748b",
                margin: "4px 0 0",
              }}
            >
              Choose where you want to study.
            </p>
          </div>
        </div>

        {libraries.length === 0 ? (
          <div
            style={{
              padding: "30px",
              textAlign: "center",
              background: "#f8fafc",
              borderRadius: "10px",
              border: "1px dashed #cbd5e1",
              color: "#64748b",
            }}
          >
            No libraries are currently available.
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fill, minmax(280px, 1fr))",
              gap: "14px",
            }}
          >
            {libraries.map((library) => {
              const isSelected =
                selectedLibrary?.id === library.id;

              return (
                <button
                  key={library.id}
                  type="button"
                  onClick={() => handleLibrarySelect(library)}
                  style={{
                    textAlign: "left",
                    background: isSelected
                      ? "#eff6ff"
                      : "#ffffff",
                    border: `1px solid ${
                      isSelected ? "#2563eb" : "#e2e8f0"
                    }`,
                    borderRadius: "10px",
                    padding: "16px",
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      fontSize: "16px",
                      fontWeight: "700",
                      color: "#0f172a",
                      marginBottom: "6px",
                    }}
                  >
                    {library.name}
                  </div>

                  <div
                    style={{
                      fontSize: "13px",
                      color: "#64748b",
                      lineHeight: "1.5",
                    }}
                  >
                    {library.address}
                  </div>

                  {library.domains_catered && (
                    <div
                      style={{
                        marginTop: "10px",
                        fontSize: "12px",
                        color: "#2563eb",
                        fontWeight: "600",
                      }}
                    >
                      {library.domains_catered}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* STEP 2 — Seats */}
      {selectedLibrary && (
        <section
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "24px",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: "1px solid #f1f5f9",
              paddingBottom: "14px",
              marginBottom: "18px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <Armchair size={22} color="#2563eb" />

              <div>
                <h2
                  style={{
                    fontSize: "18px",
                    fontWeight: "700",
                    color: "#0f172a",
                    margin: 0,
                  }}
                >
                  2. Select Seat
                </h2>

                <p
                  style={{
                    fontSize: "13px",
                    color: "#64748b",
                    margin: "4px 0 0",
                  }}
                >
                  {selectedLibrary.name}
                </p>
              </div>
            </div>

            <div
              style={{
                fontSize: "12px",
                color: "#64748b",
              }}
            >
              Available: {availableSeats.length}
            </div>
          </div>

          {isLoadingSeats ? (
            <div
              style={{
                textAlign: "center",
                padding: "30px",
                color: "#64748b",
              }}
            >
              <Loader2 size={26} color="#2563eb" />
              <div style={{ marginTop: "8px" }}>
                Loading seats...
              </div>
            </div>
          ) : seats.length === 0 ? (
            <div
              style={{
                padding: "30px",
                textAlign: "center",
                background: "#f8fafc",
                borderRadius: "10px",
                color: "#64748b",
              }}
            >
              No seats found for this library.
            </div>
          ) : (
            <>
              <div
                style={{
                  display: "flex",
                  gap: "14px",
                  marginBottom: "16px",
                  flexWrap: "wrap",
                  fontSize: "12px",
                }}
              >
                <span>🟢 Empty</span>
                <span>🟡 Reserved</span>
                <span>🔴 Occupied</span>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fill, minmax(130px, 1fr))",
                  gap: "10px",
                }}
              >
                {seats.map((seat) => {
                  const isSelected =
                    selectedSeat?.id === seat.id;

                  const isAvailable =
                    seat.status === "empty";

                  let background = "#f8fafc";
                  let border = "#e2e8f0";
                  let textColor = "#64748b";

                  if (seat.status === "empty") {
                    background = isSelected
                      ? "#dbeafe"
                      : "#f0fdf4";
                    border = isSelected
                      ? "#2563eb"
                      : "#bbf7d0";
                    textColor = "#166534";
                  }

                  if (seat.status === "reserved") {
                    background = "#fefce8";
                    border = "#fef08a";
                    textColor = "#854d0e";
                  }

                  if (seat.status === "occupied") {
                    background = "#fef2f2";
                    border = "#fecaca";
                    textColor = "#991b1b";
                  }

                  return (
                    <button
                      key={seat.id}
                      type="button"
                      disabled={!isAvailable}
                      onClick={() => handleSeatSelect(seat)}
                      style={{
                        background,
                        border: `1px solid ${border}`,
                        borderRadius: "8px",
                        padding: "14px 10px",
                        cursor: isAvailable
                          ? "pointer"
                          : "not-allowed",
                        opacity: isAvailable ? 1 : 0.75,
                        textAlign: "center",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "13px",
                          fontWeight: "700",
                          color: "#1e293b",
                          marginBottom: "5px",
                        }}
                      >
                        {seat.label}
                      </div>

                      <div
                        style={{
                          fontSize: "11px",
                          fontWeight: "700",
                          textTransform: "uppercase",
                          color: textColor,
                        }}
                      >
                        {isSelected ? "Selected" : seat.status}
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </section>
      )}

      {/* STEP 3 — Membership Plan */}
      {selectedLibrary && (
        <section
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "24px",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              borderBottom: "1px solid #f1f5f9",
              paddingBottom: "14px",
              marginBottom: "18px",
            }}
          >
            <CreditCard size={22} color="#2563eb" />

            <div>
              <h2
                style={{
                  fontSize: "18px",
                  fontWeight: "700",
                  color: "#0f172a",
                  margin: 0,
                }}
              >
                3. Select Membership Plan
              </h2>

              <p
                style={{
                  fontSize: "13px",
                  color: "#64748b",
                  margin: "4px 0 0",
                }}
              >
                Choose the plan for your seat.
              </p>
            </div>
          </div>

          {!selectedLibrary.plans ||
          selectedLibrary.plans.length === 0 ? (
            <div
              style={{
                padding: "30px",
                textAlign: "center",
                background: "#f8fafc",
                borderRadius: "10px",
                color: "#64748b",
              }}
            >
              No membership plans are available for this library.
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "repeat(auto-fill, minmax(220px, 1fr))",
                gap: "14px",
              }}
            >
              {selectedLibrary.plans.map((plan) => {
                const isSelected =
                  selectedPlan?.id === plan.id;

                return (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => handlePlanSelect(plan)}
                    style={{
                      textAlign: "left",
                      background: isSelected
                        ? "#eff6ff"
                        : "#ffffff",
                      border: `1px solid ${
                        isSelected ? "#2563eb" : "#e2e8f0"
                      }`,
                      borderRadius: "10px",
                      padding: "18px",
                      cursor: "pointer",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "16px",
                        fontWeight: "700",
                        color: "#0f172a",
                        marginBottom: "5px",
                      }}
                    >
                      {plan.name}
                    </div>

                    <div
                      style={{
                        fontSize: "13px",
                        color: "#64748b",
                        marginBottom: "12px",
                      }}
                    >
                      {plan.duration_days} days
                    </div>

                    <div
                      style={{
                        fontSize: "22px",
                        fontWeight: "800",
                        color: "#2563eb",
                      }}
                    >
                      ₹{getPlanPrice(plan)}
                    </div>

                    {isSelected && (
                      <div
                        style={{
                          marginTop: "10px",
                          fontSize: "12px",
                          fontWeight: "700",
                          color: "#2563eb",
                        }}
                      >
                        ✓ Selected
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Booking Summary */}
      {selectedSeat && selectedPlan && (
        <section
          style={{
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "20px",
            marginBottom: "20px",
          }}
        >
          <h3
            style={{
              fontSize: "16px",
              fontWeight: "700",
              color: "#0f172a",
              marginTop: 0,
              marginBottom: "14px",
            }}
          >
            Booking Summary
          </h3>

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "12px",
            }}
          >
            <div>
              <div
                style={{
                  fontSize: "12px",
                  color: "#64748b",
                }}
              >
                Library
              </div>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: "600",
                  color: "#0f172a",
                }}
              >
                {selectedLibrary?.name}
              </div>
            </div>

            <div>
              <div
                style={{
                  fontSize: "12px",
                  color: "#64748b",
                }}
              >
                Seat
              </div>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: "600",
                  color: "#0f172a",
                }}
              >
                {selectedSeat.label}
              </div>
            </div>

            <div>
              <div
                style={{
                  fontSize: "12px",
                  color: "#64748b",
                }}
              >
                Plan
              </div>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: "600",
                  color: "#0f172a",
                }}
              >
                {selectedPlan.name}
              </div>
            </div>

            <div>
              <div
                style={{
                  fontSize: "12px",
                  color: "#64748b",
                }}
              >
                Amount
              </div>
              <div
                style={{
                  fontSize: "18px",
                  fontWeight: "800",
                  color: "#2563eb",
                }}
              >
                ₹{getPlanPrice(selectedPlan)}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Book Button */}
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
        }}
      >
        <button
          type="button"
          onClick={handleBooking}
          disabled={
            isBooking ||
            !selectedLibrary ||
            !selectedSeat ||
            !selectedPlan
          }
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            background:
              isBooking ||
              !selectedLibrary ||
              !selectedSeat ||
              !selectedPlan
                ? "#94a3b8"
                : "#2563eb",
            color: "#ffffff",
            padding: "11px 22px",
            borderRadius: "8px",
            border: "none",
            fontWeight: "700",
            fontSize: "15px",
            cursor:
              isBooking ||
              !selectedLibrary ||
              !selectedSeat ||
              !selectedPlan
                ? "not-allowed"
                : "pointer",
          }}
        >
          {isBooking ? (
            <>
              <Loader2 size={18} />
              Reserving Seat...
            </>
          ) : (
            <>
              Reserve Seat & Continue
              <ArrowRight size={18} />
            </>
          )}
        </button>
      </div>

      {/* Security information */}
      <div
        style={{
          marginTop: "20px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontSize: "12px",
          color: "#64748b",
        }}
      >
        <Lock size={14} />
        Your seat will be temporarily reserved until payment is completed.
      </div>
    </div>
  );
}