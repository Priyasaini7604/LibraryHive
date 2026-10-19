import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadFile } from "@/lib/api-client";
import { admitStudent, archiveMember, fetchDues, lookupAdmission, recordRenewal } from "@/lib/api/memberships";
import { checkIn, decideVisit, downloadExport, fetchNotifications, fetchUnreadCount, respondToComplaint } from "@/lib/api/operations";
import { createBookingOrder, createRenewalOrder, verifyPayment } from "@/lib/api/payments";
import { createHold, deactivateSeat } from "@/lib/api/seats";
import { tokenStore } from "@/lib/auth";
import { ApiError } from "@/lib/errors";

const envelope = (data: unknown) => ({ success: true, data, error: null, error_code: null, details: null, request_id: "r" });
const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

describe("operations api", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    tokenStore.set("test-token");
    fetchMock.mockImplementation(async () => json(envelope({})));
  });
  afterEach(() => {
    fetchMock.mockReset();
    tokenStore.clear();
    vi.unstubAllGlobals();
  });

  const lastCall = () => {
    const [url, init] = fetchMock.mock.calls.at(-1) ?? [];
    return { url: new URL(String(url)), init: init as RequestInit, body: init?.body ? JSON.parse(String(init.body)) : undefined };
  };

  it("never sends an amount when creating an order: only the hold, or the membership and plan", async () => {
    await createBookingOrder("hold-1");
    expect(lastCall().url.pathname).toBe("/api/v1/payments/orders/");
    expect(lastCall().body).toEqual({ hold_id: "hold-1" });
    await createRenewalOrder("m-1");
    expect(lastCall().body).toEqual({ membership_id: "m-1" });
    await createRenewalOrder("m-1", "plan-2");
    expect(lastCall().body).toEqual({ membership_id: "m-1", plan_id: "plan-2" });
  });

  it("posts the three checkout values to be verified by the server", async () => {
    await verifyPayment({ razorpay_order_id: "o", razorpay_payment_id: "p", razorpay_signature: "s" });
    expect(lastCall().url.pathname).toBe("/api/v1/payments/verify/");
    expect(lastCall().body).toEqual({ razorpay_order_id: "o", razorpay_payment_id: "p", razorpay_signature: "s" });
  });

  it("holds a seat with the seat and plan ids only", async () => {
    await createHold({ seat_id: "s1", plan_id: "p1" });
    expect(lastCall().url.pathname).toBe("/api/v1/student/holds/");
    expect(lastCall().body).toEqual({ seat_id: "s1", plan_id: "p1" });
    await deactivateSeat("s1", "Broken desk");
    expect(lastCall().url.pathname).toBe("/api/v1/owner/seats/s1/deactivate/");
    expect(lastCall().body).toEqual({ reason: "Broken desk" });
  });

  it("calls the member endpoints", async () => {
    await recordRenewal("m1", { method: "cash", notes: "desk" });
    expect(lastCall().url.pathname).toBe("/api/v1/owner/members/m1/renewals/");
    expect(lastCall().body).toEqual({ method: "cash", notes: "desk" });
    await archiveMember("m1", "Left the city");
    expect(lastCall().url.pathname).toBe("/api/v1/owner/members/m1/archive/");
    await lookupAdmission({ phone: "9123456780" });
    expect(lastCall().url.pathname).toBe("/api/v1/owner/admissions/lookup/");
    await fetchDues({ status: "overdue", bucket: "8-15", page: 2 });
    expect(lastCall().url.search).toBe("?status=overdue&bucket=8-15&page=2");
  });

  it("admits a student in one request", async () => {
    await admitStudent({
      student: { name: "Asha", phone: "9123456780" },
      seat_id: "s1",
      plan_id: "p1",
      payment: { method: "cash" },
    });
    expect(lastCall().url.pathname).toBe("/api/v1/owner/admissions/");
    expect(lastCall().body.payment).toEqual({ method: "cash" });
  });

  it("calls attendance, complaint, visit and notification endpoints", async () => {
    await checkIn("lib-1");
    expect(lastCall().body).toEqual({ library_id: "lib-1" });
    await respondToComplaint("c1", { status: "resolved", owner_response: "Fixed" });
    expect(lastCall().init.method).toBe("PATCH");
    expect(lastCall().url.pathname).toBe("/api/v1/owner/complaints/c1/");
    await decideVisit("v1", { decision: "accept" });
    expect(lastCall().url.pathname).toBe("/api/v1/owner/visits/v1/decision/");
    await fetchNotifications({ unread: true });
    expect(lastCall().url.search).toBe("?unread=true");
    await fetchNotifications();
    expect(lastCall().url.search).toBe("");
    fetchMock.mockImplementationOnce(async () => json(envelope({ count: 4 })));
    await expect(fetchUnreadCount()).resolves.toBe(4);
  });

  it("downloads a CSV with the token and reads the file name", async () => {
    fetchMock.mockImplementation(async () => new Response("Name\nAsha\n", { status: 200, headers: { "Content-Disposition": 'attachment; filename="members-20261018.csv"' } }));
    const { blob, filename } = await downloadExport("members", { status: "overdue" });
    expect(filename).toBe("members-20261018.csv");
    expect(await blob.text()).toBe("Name\nAsha\n");
    const { url, init } = lastCall();
    expect(url.pathname).toBe("/api/v1/owner/exports/members.csv");
    expect(url.searchParams.get("status")).toBe("overdue");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("turns a failed download into an ApiError with the server's code", async () => {
    fetchMock.mockImplementation(async () =>
      json({ success: false, data: null, error: "Too many", error_code: "RATE_LIMITED", details: null, request_id: "r1" }, 429),
    );
    await expect(downloadFile("/owner/exports/members.csv")).rejects.toMatchObject({ code: "RATE_LIMITED", status: 429 });
    fetchMock.mockImplementation(async () => {
      throw new TypeError("offline");
    });
    await expect(downloadFile("/owner/exports/members.csv")).rejects.toBeInstanceOf(ApiError);
  });
});
