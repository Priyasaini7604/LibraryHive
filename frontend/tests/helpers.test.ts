import { describe, expect, it } from "vitest";

import { ApiError, userMessage } from "@/lib/errors";
import { formatDate, formatDateTime, formatMoney, formatPhone, relativeDue } from "@/lib/format";
import { OWNER_NAV, activeHref, homeFor, loginUrl, safeNextPath } from "@/lib/navigation";
import { buildCsp } from "@/lib/security/csp";

describe("userMessage", () => {
  it("maps known codes to friendly text", () => {
    const error = new ApiError({ status: 409, code: "SEAT_UNAVAILABLE", message: "x" });
    expect(userMessage(error)).toBe("That seat was just taken. Please pick another.");
  });

  it("adds the request reference for unexpected errors", () => {
    const error = new ApiError({ status: 500, code: "SERVER_ERROR", message: "x", requestId: "abc123" });
    expect(userMessage(error)).toBe("Something went wrong on our side. Reference: abc123");
  });

  it("never shows raw messages for unknown errors", () => {
    expect(userMessage(new Error("stack trace with secrets"))).toBe("Something went wrong on our side.");
  });
});

describe("format", () => {
  it("formats rupees in the Indian style", () => {
    expect(formatMoney("1200.00")).toBe("₹1,200");
    expect(formatMoney("150000")).toBe("₹1,50,000");
    expect(formatMoney("1200.50")).toBe("₹1,200.50");
  });

  it("formats business dates without shifting the day", () => {
    expect(formatDate("2026-10-09")).toBe("9 Oct 2026");
  });

  it("shows datetimes in India time regardless of device time zone", () => {
    expect(formatDateTime("2026-10-08T20:00:00Z")).toMatch(/9 Oct 2026, 1:30\s?am/i);
  });

  it("describes due dates relative to today", () => {
    expect(relativeDue("2026-10-12", "2026-10-09")).toBe("due in 3 days");
    expect(relativeDue("2026-10-09", "2026-10-09")).toBe("due today");
    expect(relativeDue("2026-10-07", "2026-10-09")).toBe("2 days overdue");
  });

  it("formats Indian mobile numbers", () => {
    expect(formatPhone("+919876543210")).toBe("+91 98765 43210");
  });
});

describe("navigation", () => {
  it("accepts only same-origin relative next paths", () => {
    expect(safeNextPath("/owner/seats")).toBe("/owner/seats");
    expect(safeNextPath("//evil.com")).toBeNull();
    expect(safeNextPath("/\\evil.com")).toBeNull();
    expect(safeNextPath("https://evil.com")).toBeNull();
    expect(safeNextPath(null)).toBeNull();
  });

  it("routes each role to its home and builds login links", () => {
    expect(homeFor("owner")).toBe("/owner");
    expect(homeFor("student")).toBe("/student");
    expect(loginUrl("/owner/seats")).toBe("/login?next=%2Fowner%2Fseats");
  });

  it("highlights the most specific navigation item", () => {
    expect(activeHref("/owner/members/123", OWNER_NAV)).toBe("/owner/members");
    expect(activeHref("/owner", OWNER_NAV)).toBe("/owner");
  });
});

describe("Content-Security-Policy", () => {
  const csp = buildCsp({ nonce: "abc", apiUrl: "https://api.example.com/api/v1", isDev: false });

  it("allows scripts only with the nonce", () => {
    expect(csp).toContain("script-src 'self' 'nonce-abc' 'strict-dynamic'");
    expect(csp).not.toContain("unsafe-eval");
  });

  it("allows API calls to the backend origin only", () => {
    expect(csp).toContain("connect-src 'self' https://api.example.com");
  });

  it("blocks framing, plugins and base-tag hijacking", () => {
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
  });

  it("permits eval only in development", () => {
    expect(buildCsp({ nonce: "n", apiUrl: "http://localhost:8000", isDev: true })).toContain("'unsafe-eval'");
  });
});
