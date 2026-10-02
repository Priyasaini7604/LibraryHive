"use client";



import React, { useEffect, useState } from "react";

import { useRouter } from "next/navigation";



import { apiClient } from "@/lib/api-client";

import { authStorage } from "@/lib/auth";

import { Membership, User } from "@/lib/types";



import {

  CreditCard,

  CalendarDays,

  Armchair,

  CheckCircle2,

  AlertCircle,

  Loader2,

  ArrowLeft,

  RefreshCw,

} from "lucide-react";



export default function StudentMembershipPage() {

  const router = useRouter();



  const [memberships, setMemberships] = useState<Membership[]>([]);

  const [user, setUser] = useState<User | null>(null);

  const [isLoading, setIsLoading] = useState(true);



  const [renewingMembershipId, setRenewingMembershipId] =

    useState<string | null>(null);



  const [feedback, setFeedback] = useState<{

    type: "success" | "error";

    message: string;

  } | null>(null);



  useEffect(() => {

    loadMemberships();

  }, []);



  const loadMemberships = async () => {

    setIsLoading(true);

    setFeedback(null);



    const token = authStorage.getAccessToken();



    if (!token) {

      setFeedback({

        type: "error",

        message: "Please login before viewing your membership.",

      });



      setIsLoading(false);

      return;

    }



    try {

      const currentUser = authStorage.getUser();



      if (currentUser) {

        setUser(currentUser);

      }



      const data = await apiClient.getMemberships();



      setMemberships(data);

    } catch (err: any) {

      setFeedback({

        type: "error",

        message:

          err.message || "Failed to load your memberships.",

      });

    } finally {

      setIsLoading(false);

    }

  };



  // ---------------------------------------------------------

  // Load Razorpay checkout script

  // ---------------------------------------------------------



  const loadRazorpayScript = (): Promise<boolean> => {

    return new Promise((resolve) => {

      if (window.Razorpay) {

        resolve(true);

        return;

      }



      const existingScript = document.querySelector(

        'script[src="https://checkout.razorpay.com/v1/checkout.js"]'

      );



      if (existingScript) {

        existingScript.addEventListener("load", () =>

          resolve(true)

        );



        existingScript.addEventListener("error", () =>

          resolve(false)

        );



        return;

      }



      const script = document.createElement("script");



      script.src =

        "https://checkout.razorpay.com/v1/checkout.js";



      script.onload = () => resolve(true);

      script.onerror = () => resolve(false);



      document.body.appendChild(script);

    });

  };



  // ---------------------------------------------------------

  // Renew membership

  // ---------------------------------------------------------



  const handleRenew = async (

    membership: Membership

  ) => {



    if (renewingMembershipId) {

      return;

    }



    setFeedback(null);

    setRenewingMembershipId(membership.id);



    try {

      const razorpayLoaded =

        await loadRazorpayScript();



      if (!razorpayLoaded) {

        throw new Error(

          "Razorpay checkout could not be loaded. Please check your internet connection and try again."

        );

      }



      // Create Razorpay order from backend

      const order =

        await apiClient.createRenewalPaymentOrder(

          membership.id

        );



      const options = {

        key: order.key_id,



        amount: Number(order.amount) * 100,



        currency: order.currency || "INR",



        name: "LibraryHive",



        description: `Membership renewal - ${membership.plan}`,



        order_id: order.order_id,



        handler: async (response: {

          razorpay_order_id: string;

          razorpay_payment_id: string;

          razorpay_signature: string;

        }) => {

          try {

            setFeedback({

              type: "success",

              message:

                "Payment received. Verifying your payment...",

            });



            const result =

              await apiClient.verifyRenewalPayment({

                razorpay_order_id:

                  response.razorpay_order_id,



                razorpay_payment_id:

                  response.razorpay_payment_id,



                razorpay_signature:

                  response.razorpay_signature,

              });



            setFeedback({

              type: "success",

              message: `Membership renewed successfully. Your next due date is ${formatDate(

                result.next_due_date

              )}.`,

            });



            await loadMemberships();

          } catch (err: any) {

            setFeedback({

              type: "error",

              message:

                err.message ||

                "Payment verification failed. Please contact support if money was deducted.",

            });

          } finally {

            setRenewingMembershipId(null);

          }

        },



        prefill: {

          name: user?.name || "",

          email: user?.email || "",

          contact: user?.phone || "",

        },



        theme: {

          color: "#2563eb",

        },



        modal: {

          ondismiss: () => {

            setRenewingMembershipId(null);



            setFeedback({

              type: "error",

              message:

                "Payment was cancelled. Your membership has not been renewed.",

            });

          },

        },

      };



      const razorpay =

        new window.Razorpay(options);



      razorpay.open();

    } catch (err: any) {

      setRenewingMembershipId(null);



      setFeedback({

        type: "error",

        message:

          err.message ||

          "Unable to start membership renewal.",

      });

    }

  };



  // ---------------------------------------------------------

  // Status helpers

  // ---------------------------------------------------------



  const getStatusStyle = (

    status: Membership["status"]

  ) => {

    switch (status) {

      case "active":

        return {

          background: "#dcfce7",

          color: "#166534",

          border: "#bbf7d0",

        };



      case "due":

        return {

          background: "#fefce8",

          color: "#854d0e",

          border: "#fef08a",

        };



      case "overdue":

        return {

          background: "#fee2e2",

          color: "#991b1b",

          border: "#fecaca",

        };



      case "archived":

        return {

          background: "#f1f5f9",

          color: "#475569",

          border: "#cbd5e1",

        };



      default:

        return {

          background: "#f1f5f9",

          color: "#475569",

          border: "#cbd5e1",

        };

    }

  };



  const formatStatus = (

    status: Membership["status"]

  ) => {

    return (

      status.charAt(0).toUpperCase() +

      status.slice(1)

    );

  };



  const formatDate = (date: string) => {

    const parsedDate = new Date(date);



    if (Number.isNaN(parsedDate.getTime())) {

      return date;

    }



    return parsedDate.toLocaleDateString("en-IN", {

      day: "2-digit",

      month: "short",

      year: "numeric",

    });

  };



  // ---------------------------------------------------------

  // Loading

  // ---------------------------------------------------------



  if (isLoading) {

    return (

      <div

        style={{

          maxWidth: "900px",

          margin: "70px auto",

          padding: "0 20px",

          textAlign: "center",

        }}

      >

        <Loader2

          size={32}

          color="#2563eb"

        />



        <p

          style={{

            marginTop: "12px",

            color: "#64748b",

            fontSize: "14px",

          }}

        >

          Loading your memberships...

        </p>

      </div>

    );

  }



  // ---------------------------------------------------------

  // Page

  // ---------------------------------------------------------



  return (

    <div

      style={{

        maxWidth: "1000px",

        margin: "36px auto",

        padding: "0 20px 50px",

      }}

    >

      {/* Header */}



      <div

        style={{

          marginBottom: "24px",

        }}

      >

        <button

          type="button"

          onClick={() =>

            router.push("/student/book")

          }

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

            fontSize: "14px",

          }}

        >

          <ArrowLeft size={16} />



          Book Another Seat

        </button>



        <div

          style={{

            display: "flex",

            alignItems: "center",

            gap: "10px",

          }}

        >

          <CreditCard

            size={28}

            color="#2563eb"

          />



          <h1

            style={{

              fontSize: "28px",

              fontWeight: "800",

              color: "#0f172a",

              margin: 0,

            }}

          >

            My Memberships

          </h1>

        </div>



        {user && (

          <p

            style={{

              color: "#64748b",

              fontSize: "14px",

              marginTop: "8px",

            }}

          >

            Memberships for {user.name}

          </p>

        )}

      </div>



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



      {/* Refresh */}



      <div

        style={{

          display: "flex",

          justifyContent: "flex-end",

          marginBottom: "14px",

        }}

      >

        <button

          type="button"

          onClick={loadMemberships}

          disabled={!!renewingMembershipId}

          style={{

            display: "flex",

            alignItems: "center",

            gap: "7px",

            background: "#ffffff",

            border: "1px solid #cbd5e1",

            borderRadius: "7px",

            padding: "8px 13px",

            color: "#475569",

            fontWeight: "600",

            cursor: renewingMembershipId

              ? "not-allowed"

              : "pointer",

            fontSize: "13px",

            opacity: renewingMembershipId

              ? 0.6

              : 1,

          }}

        >

          <RefreshCw size={15} />



          Refresh

        </button>

      </div>



      {/* Empty state */}



      {memberships.length === 0 ? (

        <div

          style={{

            background: "#ffffff",

            border: "1px solid #e2e8f0",

            borderRadius: "14px",

            padding: "50px 25px",

            textAlign: "center",

          }}

        >

          <div

            style={{

              width: "58px",

              height: "58px",

              borderRadius: "50%",

              background: "#eff6ff",

              display: "flex",

              alignItems: "center",

              justifyContent: "center",

              margin: "0 auto 16px",

            }}

          >

            <CreditCard

              size={28}

              color="#2563eb"

            />

          </div>



          <h2

            style={{

              fontSize: "19px",

              fontWeight: "700",

              color: "#0f172a",

              margin: "0 0 8px",

            }}

          >

            No memberships yet

          </h2>



          <p

            style={{

              color: "#64748b",

              fontSize: "14px",

              marginBottom: "20px",

            }}

          >

            Book a library seat and complete payment

            to create your membership.

          </p>



          <button

            type="button"

            onClick={() =>

              router.push("/student/book")

            }

            style={{

              background: "#2563eb",

              color: "#ffffff",

              border: "none",

              borderRadius: "8px",

              padding: "10px 18px",

              fontWeight: "700",

              cursor: "pointer",

            }}

          >

            Find a Seat

          </button>

        </div>

      ) : (

        <div

          style={{

            display: "grid",

            gap: "18px",

          }}

        >

          {memberships.map((membership) => {

            const statusStyle =

              getStatusStyle(

                membership.status

              );



            const isRenewing =

              renewingMembershipId ===

              membership.id;



            const canRenew =

              membership.status === "active" ||

              membership.status === "due" ||

              membership.status === "overdue";



            return (

              <div

                key={membership.id}

                style={{

                  background: "#ffffff",

                  border:

                    "1px solid #e2e8f0",

                  borderRadius: "14px",

                  overflow: "hidden",

                }}

              >

                {/* Membership header */}



                <div

                  style={{

                    padding: "18px 20px",

                    borderBottom:

                      "1px solid #f1f5f9",

                    display: "flex",

                    justifyContent:

                      "space-between",

                    alignItems: "center",

                    gap: "15px",

                    flexWrap: "wrap",

                  }}

                >

                  <div

                    style={{

                      display: "flex",

                      alignItems: "center",

                      gap: "10px",

                    }}

                  >

                    <div

                      style={{

                        width: "42px",

                        height: "42px",

                        borderRadius: "9px",

                        background: "#eff6ff",

                        display: "flex",

                        alignItems:

                          "center",

                        justifyContent:

                          "center",

                      }}

                    >

                      <CreditCard

                        size={21}

                        color="#2563eb"

                      />

                    </div>



                    <div>

                      <div

                        style={{

                          fontSize: "17px",

                          fontWeight: "700",

                          color: "#0f172a",

                        }}

                      >

                        Membership

                      </div>



                      <div

                        style={{

                          fontSize: "12px",

                          color: "#94a3b8",

                          marginTop: "2px",

                        }}

                      >

                        ID: {membership.id}

                      </div>

                    </div>

                  </div>



                  <span

                    style={{

                      background:

                        statusStyle.background,

                      color:

                        statusStyle.color,

                      border: `1px solid ${statusStyle.border}`,

                      borderRadius: "20px",

                      padding: "5px 12px",

                      fontSize: "12px",

                      fontWeight: "700",

                    }}

                  >

                    {formatStatus(

                      membership.status

                    )}

                  </span>

                </div>



                {/* Membership details */}



                <div

                  style={{

                    padding: "20px",

                    display: "grid",

                    gridTemplateColumns:

                      "repeat(auto-fit, minmax(200px, 1fr))",

                    gap: "18px",

                  }}

                >

                  {/* Seat */}



                  <div

                    style={{

                      display: "flex",

                      alignItems:

                        "flex-start",

                      gap: "10px",

                    }}

                  >

                    <Armchair

                      size={19}

                      color="#2563eb"

                    />



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

                          fontSize: "15px",

                          fontWeight: "700",

                          color: "#0f172a",

                          marginTop: "3px",

                        }}

                      >

                        {membership.seat}

                      </div>

                    </div>

                  </div>



                  {/* Plan */}



                  <div

                    style={{

                      display: "flex",

                      alignItems:

                        "flex-start",

                      gap: "10px",

                    }}

                  >

                    <CreditCard

                      size={19}

                      color="#2563eb"

                    />



                    <div>

                      <div

                        style={{

                          fontSize: "12px",

                          color: "#64748b",

                        }}

                      >

                        Membership Plan

                      </div>



                      <div

                        style={{

                          fontSize: "15px",

                          fontWeight: "700",

                          color: "#0f172a",

                          marginTop: "3px",

                        }}

                      >

                        {membership.plan}

                      </div>

                    </div>

                  </div>



                  {/* Start Date */}



                  <div

                    style={{

                      display: "flex",

                      alignItems:

                        "flex-start",

                      gap: "10px",

                    }}

                  >

                    <CalendarDays

                      size={19}

                      color="#2563eb"

                    />



                    <div>

                      <div

                        style={{

                          fontSize: "12px",

                          color: "#64748b",

                        }}

                      >

                        Start Date

                      </div>



                      <div

                        style={{

                          fontSize: "15px",

                          fontWeight: "700",

                          color: "#0f172a",

                          marginTop: "3px",

                        }}

                      >

                        {formatDate(

                          membership.start_date

                        )}

                      </div>

                    </div>

                  </div>



                  {/* Next Due Date */}



                  <div

                    style={{

                      display: "flex",

                      alignItems:

                        "flex-start",

                      gap: "10px",

                    }}

                  >

                    <CalendarDays

                      size={19}

                      color={

                        membership.status ===

                        "overdue"

                          ? "#dc2626"

                          : "#2563eb"

                      }

                    />



                    <div>

                      <div

                        style={{

                          fontSize: "12px",

                          color: "#64748b",

                        }}

                      >

                        Next Due Date

                      </div>



                      <div

                        style={{

                          fontSize: "15px",

                          fontWeight: "700",

                          color:

                            membership.status ===

                            "overdue"

                              ? "#dc2626"

                              : "#0f172a",

                          marginTop: "3px",

                        }}

                      >

                        {formatDate(

                          membership.next_due_date

                        )}

                      </div>

                    </div>

                  </div>

                </div>



                {/* Renewal section */}



                {canRenew && (

                  <div

                    style={{

                      padding: "14px 20px",

                      borderTop:

                        "1px solid #f1f5f9",

                      display: "flex",

                      justifyContent:

                        "space-between",

                      alignItems: "center",

                      gap: "12px",

                      flexWrap: "wrap",

                      background: "#f8fafc",

                    }}

                  >

                    <div>

                      <div

                        style={{

                          fontSize: "13px",

                          fontWeight: "700",

                          color: "#0f172a",

                        }}

                      >

                        {membership.status ===

                        "overdue"

                          ? "Your membership is overdue"

                          : "Renew your membership"}

                      </div>



                      <div

                        style={{

                          fontSize: "12px",

                          color: "#64748b",

                          marginTop: "3px",

                        }}

                      >

                        Pay securely using Razorpay.

                      </div>

                    </div>



                    <button

                      type="button"

                      onClick={() =>

                        handleRenew(

                          membership

                        )

                      }

                      disabled={

                        !!renewingMembershipId

                      }

                      style={{

                        display: "flex",

                        alignItems:

                          "center",

                        justifyContent:

                          "center",

                        gap: "7px",

                        background:

                          renewingMembershipId

                            ? "#94a3b8"

                            : "#2563eb",

                        color: "#ffffff",

                        border: "none",

                        borderRadius: "8px",

                        padding:

                          "10px 18px",

                        fontWeight: "700",

                        cursor:

                          renewingMembershipId

                            ? "not-allowed"

                            : "pointer",

                        fontSize: "13px",

                        minWidth: "150px",

                      }}

                    >

                      {isRenewing ? (

                        <>

                          <Loader2

                            size={15}

                            className="animate-spin"

                          />

                          Processing...

                        </>

                      ) : (

                        <>

                          <CreditCard

                            size={15}

                          />

                          Renew Membership

                        </>

                      )}

                    </button>

                  </div>

                )}



                {/* Footer */}



                {!canRenew && (

                  <div

                    style={{

                      background:

                        "#f8fafc",

                      borderTop:

                        "1px solid #f1f5f9",

                      padding:

                        "13px 20px",

                      fontSize: "12px",

                      color: "#64748b",

                    }}

                  >

                    Archived memberships

                    cannot be renewed.

                  </div>

                )}



                {canRenew && (

                  <div

                    style={{

                      background:

                        "#ffffff",

                      borderTop:

                        "1px solid #f1f5f9",

                      padding:

                        "13px 20px",

                      fontSize: "12px",

                      color: "#64748b",

                    }}

                  >

                    Membership status and

                    renewal information are

                    shown above.

                  </div>

                )}

              </div>

            );

          })}

        </div>

      )}

    </div>

  );

}
