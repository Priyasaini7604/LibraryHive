"use client";

import React, { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { authStorage } from "@/lib/auth";
import {
  BookOpen,
  Mail,
  Lock,
  LogIn,
  AlertCircle,
  Loader2,
} from "lucide-react";

export default function StudentLoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [isLoading, setIsLoading] = useState(false);

  const [error, setError] = useState("");

  const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setIsLoading(true);

    try {
      const response = await apiClient.login({
        email: email.trim(),
        password,
      });

      /*
       * apiClient.login() already stores the JWT tokens
       * and user information in authStorage.
       */
      if (response.user) {
        authStorage.setUser(response.user);
      }

      router.push("/student/book");
    } catch (err: any) {
      setError(
        err.message ||
          "Login failed. Please check your email and password."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "calc(100vh - 67px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 20px",
        background: "#f8fafc",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "430px",
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "14px",
          padding: "32px",
          boxShadow: "0 8px 30px rgba(15, 23, 42, 0.06)",
        }}
      >
        {/* Header */}
        <div
          style={{
            textAlign: "center",
            marginBottom: "26px",
          }}
        >
          <div
            style={{
              width: "52px",
              height: "52px",
              borderRadius: "12px",
              background: "#eff6ff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 14px",
            }}
          >
            <BookOpen size={27} color="#2563eb" />
          </div>

          <h1
            style={{
              fontSize: "24px",
              fontWeight: "800",
              color: "#0f172a",
              margin: 0,
            }}
          >
            Student Login
          </h1>

          <p
            style={{
              fontSize: "14px",
              color: "#64748b",
              marginTop: "7px",
            }}
          >
            Login to book your library seat.
          </p>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "9px",
              background: "#fee2e2",
              border: "1px solid #fecaca",
              color: "#991b1b",
              borderRadius: "8px",
              padding: "12px 14px",
              marginBottom: "18px",
              fontSize: "13px",
            }}
          >
            <AlertCircle
              size={17}
              style={{
                flexShrink: 0,
                marginTop: "1px",
              }}
            />

            <span>{error}</span>
          </div>
        )}

        {/* Login form */}
        <form onSubmit={handleLogin}>
          {/* Email */}
          <div style={{ marginBottom: "18px" }}>
            <label
              htmlFor="email"
              style={{
                display: "block",
                fontSize: "14px",
                fontWeight: "600",
                color: "#334155",
                marginBottom: "7px",
              }}
            >
              Email
            </label>

            <div
              style={{
                position: "relative",
              }}
            >
              <Mail
                size={18}
                color="#94a3b8"
                style={{
                  position: "absolute",
                  left: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              />

              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="student@test.com"
                autoComplete="email"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "11px 12px 11px 40px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "14px",
                  outline: "none",
                }}
              />
            </div>
          </div>

          {/* Password */}
          <div style={{ marginBottom: "20px" }}>
            <label
              htmlFor="password"
              style={{
                display: "block",
                fontSize: "14px",
                fontWeight: "600",
                color: "#334155",
                marginBottom: "7px",
              }}
            >
              Password
            </label>

            <div
              style={{
                position: "relative",
              }}
            >
              <Lock
                size={18}
                color="#94a3b8"
                style={{
                  position: "absolute",
                  left: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              />

              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "11px 12px 11px 40px",
                  borderRadius: "8px",
                  border: "1px solid #cbd5e1",
                  fontSize: "14px",
                  outline: "none",
                }}
              />
            </div>
          </div>

          {/* Login button */}
          <button
            type="submit"
            disabled={isLoading}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              background: isLoading ? "#94a3b8" : "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              padding: "12px",
              fontSize: "15px",
              fontWeight: "700",
              cursor: isLoading ? "not-allowed" : "pointer",
            }}
          >
            {isLoading ? (
              <>
                <Loader2 size={18} />
                Logging in...
              </>
            ) : (
              <>
                <LogIn size={18} />
                Login as Student
              </>
            )}
          </button>
        </form>

        {/* Test credentials */}
        <div
          style={{
            marginTop: "22px",
            padding: "13px 14px",
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
          }}
        >
          <div
            style={{
              fontSize: "12px",
              fontWeight: "700",
              color: "#475569",
              marginBottom: "6px",
            }}
          >
            Test Student
          </div>

          <div
            style={{
              fontSize: "12px",
              color: "#64748b",
              lineHeight: "1.7",
            }}
          >
            Email: student@test.com
            <br />
            Password: Test@12345
          </div>
        </div>
      </div>
    </div>
  );
}