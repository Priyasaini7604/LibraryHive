"use client";

import React, { useEffect, useState } from "react";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { authStorage } from "@/lib/auth";
import { Booking, User } from "@/lib/types";
import {
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowLeft,
  ShieldCheck,
} from "lucide-react";

export default function StudentPaymentPage() {
  const router = useRouter();

  const [booking, setBooking] = useState<Booking | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingOrder, setIsCreatingOrder] = useState(false);
  const [isPaymentSuccessful, setIsPaymentSuccessful] = useState(false);

  const [paymentDetails, setPaymentDetails] = useState<{
    amount: number | string;
    currency: string;
    next_due_date?: string;
  } | null>(null);

  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    loadBooking();
  }, []);

  const loadBooking = () => {
    const token = authStorage.getAccessToken();

    if (!token) {
      setFeedback({
        type: "error",
        message: "Please login before making a payment.",
      });
      setIsLoading(false);
      return;
    }

    const currentUser = authStorage.getUser();

    if (currentUser) {
      setUser(currentUser);
    }

    const storedBooking = sessionStorage.getItem(
      "libraryhive_pending_booking"
    );

    if (!storedBooking) {
      setFeedback({
        type: "error",
        message:
          "No pending booking was found. Please create a booking first.",
      });
      setIsLoading(false);
      return;
    }

    try {
      const parsedBooking: Booking = JSON.parse(storedBooking);
      setBooking(parsedBooking);
    } catch {
      setFeedback({
        type: "error",
        message: "The pending booking information is invalid.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const startPayment = async () => {
    if (!booking) {
      setFeedback({
        type: "error",
        message: "No booking available for payment.",
      });
      return;
    }

    if (!window.Razorpay) {
      setFeedback({
        type: "error",
        message:
          "Payment system is still loading. Please wait a moment and try again.",
      });
      return;
    }

    setIsCreatingOrder(true);
    setFeedback(null);

    try {
      const order = await apiClient.createPaymentOrder(booking.id);

      setPaymentDetails({
        amount: order.amount,
        currency: order.currency,
      });

      const options: RazorpayOptions = {
        key: order.key_id,
        amount: Number(order.amount) * 100,
        currency: order.currency,
        name: "LibraryHive",
        description: "Library Membership Payment",
        order_id: order.order_id,

        prefill: {
          name: user?.name,
          email: user?.email,
          contact: user?.phone,
        },

        theme: {
          color: "#2563eb",
        },

        modal: {
          ondismiss: () => {
            setIsCreatingOrder(false);

            setFeedback({
              type: "error",
              message:
                "Payment window was closed. Your seat remains reserved until the reservation expires.",
            });
          },
        },

        handler: async (response) => {
          try {
            setFeedback(null);

            const verification = await apiClient.verifyPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });

            setIsPaymentSuccessful(true);

            setPaymentDetails({
              amount: order.amount,
              currency: order.currency,
              next_due_date: verification.next_due_date,
            });

            sessionStorage.removeItem(
              "libraryhive_pending_booking"
            );

            setFeedback({
              type: "success",
              message:
                "Payment verified successfully. Your membership is now active.",
            });
          } catch (err: any) {
            setFeedback({
              type: "error",
              message:
                err.message ||
                "Payment was completed, but verification failed. Please contact support.",
            });
          } finally {
            setIsCreatingOrder(false);
          }
        },
      };

      const razorpay = new window.Razorpay(options);

      razorpay.open();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message:
          err.message ||
          "Unable to create the payment order. Please try again.",
      });

      setIsCreatingOrder(false);
    }
  };

  if (isLoading) {
    return (
      <div
        style={{
          maxWidth: "700px",
          margin: "70px auto",
          padding: "0 20px",
          textAlign: "center",
        }}
      >
        <Loader2 size={32} color="#2563eb" />

        <p
          style={{
            marginTop: "12px",
            color: "#64748b",
          }}
        >
          Loading payment details...
        </p>
      </div>
    );
  }

  return (
    <>
      {/* Razorpay Checkout script */}
      <Script
        src="https://checkout.razorpay.com/v1/checkout.js"
        strategy="afterInteractive"
      />

      <div
        style={{
          maxWidth: "700px",
          margin: "40px auto",
          padding: "0 20px 50px",
        }}
      >
        {/* Page heading */}
        <div
          style={{
            marginBottom: "24px",
          }}
        >
          <button
            type="button"
            onClick={() => router.push("/student/book")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              border: "none",
              background: "transparent",
              color: "#64748b",
              cursor: "pointer",
              padding: 0,
              marginBottom: "14px",
            }}
          >
            <ArrowLeft size={16} />
            Back to Booking
          </button>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <CreditCard size={28} color="#2563eb" />

            <h1
              style={{
                fontSize: "28px",
                fontWeight: "800",
                color: "#0f172a",
                margin: 0,
              }}
            >
              Complete Payment
            </h1>
          </div>

          <p
            style={{
              marginTop: "8px",
              color: "#64748b",
              fontSize: "14px",
            }}
          >
            Complete your membership payment to confirm your seat.
          </p>
        </div>

        {/* Feedback */}
        {feedback && (
          <div
            style={{
              padding: "14px 18px",
              borderRadius: "8px",
              marginBottom: "20px",
              display: "flex",
              alignItems: "flex-start",
              gap: "10px",
              background:
                feedback.type === "success"
                  ? "#dcfce7"
                  : "#fee2e2",
              border:
                feedback.type === "success"
                  ? "1px solid #bbf7d0"
                  : "1px solid #fecaca",
              color:
                feedback.type === "success"
                  ? "#166534"
                  : "#991b1b",
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

        {/* Success card */}
        {isPaymentSuccessful ? (
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #bbf7d0",
              borderRadius: "14px",
              padding: "30px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: "60px",
                height: "60px",
                borderRadius: "50%",
                background: "#dcfce7",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 18px",
              }}
            >
              <CheckCircle2 size={34} color="#16a34a" />
            </div>

            <h2
              style={{
                fontSize: "22px",
                fontWeight: "800",
                color: "#166534",
                margin: "0 0 8px",
              }}
            >
              Payment Successful!
            </h2>

            <p
              style={{
                color: "#64748b",
                fontSize: "14px",
                marginBottom: "24px",
              }}
            >
              Your seat has been confirmed and your membership is active.
            </p>

            {paymentDetails?.next_due_date && (
              <div
                style={{
                  background: "#f8fafc",
                  borderRadius: "10px",
                  padding: "16px",
                  marginBottom: "20px",
                }}
              >
                <div
                  style={{
                    fontSize: "12px",
                    color: "#64748b",
                  }}
                >
                  Next Payment Due
                </div>

                <div
                  style={{
                    fontSize: "18px",
                    fontWeight: "700",
                    color: "#0f172a",
                    marginTop: "4px",
                  }}
                >
                  {paymentDetails.next_due_date}
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={() => router.push("/student/membership")}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                padding: "11px 20px",
                fontWeight: "700",
                cursor: "pointer",
              }}
            >
              View My Membership
            </button>
          </div>
        ) : (
          <>
            {/* Payment summary */}
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "14px",
                padding: "24px",
                marginBottom: "18px",
              }}
            >
              <h2
                style={{
                  fontSize: "18px",
                  fontWeight: "700",
                  color: "#0f172a",
                  marginTop: 0,
                  marginBottom: "18px",
                }}
              >
                Payment Summary
              </h2>

              <div
                style={{
                  display: "grid",
                  gap: "14px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: "20px",
                  }}
                >
                  <span
                    style={{
                      color: "#64748b",
                      fontSize: "14px",
                    }}
                  >
                    Booking ID
                  </span>

                  <span
                    style={{
                      color: "#0f172a",
                      fontSize: "13px",
                      fontWeight: "600",
                      wordBreak: "break-all",
                      textAlign: "right",
                    }}
                  >
                    {booking?.id}
                  </span>
                </div>

                <div
                  style={{
                    borderTop: "1px solid #f1f5f9",
                  }}
                />

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span
                    style={{
                      color: "#64748b",
                      fontSize: "14px",
                    }}
                  >
                    Amount
                  </span>

                  <span
                    style={{
                      color: "#2563eb",
                      fontSize: "26px",
                      fontWeight: "800",
                    }}
                  >
                    ₹
                    {paymentDetails
                      ? Number(paymentDetails.amount).toLocaleString(
                          "en-IN"
                        )
                      : "—"}
                  </span>
                </div>
              </div>
            </div>

            {/* Payment security */}
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: "10px",
                padding: "14px 16px",
                marginBottom: "20px",
              }}
            >
              <ShieldCheck
                size={20}
                color="#2563eb"
                style={{ flexShrink: 0 }}
              />

              <div>
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: "700",
                    color: "#1e40af",
                  }}
                >
                  Secure Payment
                </div>

                <div
                  style={{
                    fontSize: "12px",
                    color: "#475569",
                    marginTop: "3px",
                  }}
                >
                  Your payment is securely processed through Razorpay.
                </div>
              </div>
            </div>

            {/* Pay button */}
            <button
              type="button"
              onClick={startPayment}
              disabled={isCreatingOrder || !booking}
              style={{
                width: "100%",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gap: "8px",
                background:
                  isCreatingOrder || !booking
                    ? "#94a3b8"
                    : "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "9px",
                padding: "13px 20px",
                fontSize: "15px",
                fontWeight: "700",
                cursor:
                  isCreatingOrder || !booking
                    ? "not-allowed"
                    : "pointer",
              }}
            >
              {isCreatingOrder ? (
                <>
                  <Loader2 size={18} />
                  Opening Payment...
                </>
              ) : (
                <>
                  <CreditCard size={18} />
                  Pay with Razorpay
                </>
              )}
            </button>

            <p
              style={{
                textAlign: "center",
                color: "#94a3b8",
                fontSize: "11px",
                marginTop: "12px",
              }}
            >
              Complete payment before your seat reservation expires.
            </p>
          </>
        )}
      </div>
    </>
  );
}