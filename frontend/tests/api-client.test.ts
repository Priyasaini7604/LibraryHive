import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, buildUrl, onSessionExpired, request, serverNow } from "@/lib/api-client";
import { tokenStore } from "@/lib/auth";
import { ApiError, NETWORK_ERROR } from "@/lib/errors";

function envelopeResponse(
  status: number,
  body: { success: boolean; data?: unknown; error?: string; error_code?: string; details?: unknown },
  headers: Record<string, string> = {},
): Response {
  return new Response(
    JSON.stringify({ data: null, error: null, error_code: null, details: null, request_id: "req-1", ...body }),
    { status, headers: { "Content-Type": "application/json", ...headers } },
  );
}

const ok = (data: unknown, headers?: Record<string, string>) => envelopeResponse(200, { success: true, data }, headers);
const unauthorized = () =>
  envelopeResponse(401, { success: false, error: "Expired", error_code: "TOKEN_INVALID" });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  tokenStore.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  onSessionExpired(null);
});

describe("buildUrl", () => {
  it("sends auth calls to the frontend origin (SEC-1 proxy) and others to the API", () => {
    expect(buildUrl("/auth/me/")).toBe("/api/v1/auth/me/");
    expect(buildUrl("/libraries/")).toBe("http://127.0.0.1:8000/api/v1/libraries/");
  });

  it("encodes query parameters, repeats arrays and skips empty values", () => {
    expect(buildUrl("/libraries/", { amenity: ["ac", "wifi"], search: "", page: 2, domain: undefined })).toBe(
      "http://127.0.0.1:8000/api/v1/libraries/?amenity=ac&amenity=wifi&page=2",
    );
  });
});

describe("request", () => {
  it("unwraps the envelope and sends the access token", async () => {
    tokenStore.set("access-1");
    fetchMock.mockResolvedValueOnce(ok({ id: "x" }));

    await expect(api.get("/libraries/x/")).resolves.toEqual({ id: "x" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer access-1");
    expect(init.credentials).toBe("omit");
  });

  it("uses same-origin credentials only for auth endpoints", async () => {
    fetchMock.mockResolvedValueOnce(ok({ access: "a", user: {} }));
    await api.post("/auth/login/", { email: "a@b.com", password: "x" }, { auth: false });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/login/");
    expect(init.credentials).toBe("same-origin");
  });

  it("throws ApiError with the backend's code, details and request id", async () => {
    fetchMock.mockResolvedValueOnce(
      envelopeResponse(400, {
        success: false,
        error: "Please correct the highlighted fields.",
        error_code: "VALIDATION_ERROR",
        details: { phone: ["Invalid"] },
      }),
    );
    const error = (await api.post("/x/", {}).catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.details).toEqual({ phone: ["Invalid"] });
    expect(error.requestId).toBe("req-1");
  });

  it("reports network failures with a dedicated code", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(api.get("/x/")).rejects.toMatchObject({ code: NETWORK_ERROR, status: 0 });
  });

  it("does not set a JSON content type for multipart uploads", async () => {
    fetchMock.mockResolvedValueOnce(ok({}));
    await api.post("/owner/library/photos/", new FormData());
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("tracks the server clock from the Date header", async () => {
    const serverDate = new Date(Date.now() + 120_000);
    fetchMock.mockResolvedValueOnce(ok({}, { Date: serverDate.toUTCString() }));
    await api.get("/x/");
    expect(Math.abs(serverNow() - serverDate.getTime())).toBeLessThan(2_000);
  });
});

describe("refresh on 401", () => {
  it("refreshes once and retries the request with the new token", async () => {
    tokenStore.set("expired");
    fetchMock
      .mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(ok({ access: "fresh" }))
      .mockResolvedValueOnce(ok({ id: "x" }));

    await expect(api.get("/owner/seats/")).resolves.toEqual({ id: "x" });

    const urls = fetchMock.mock.calls.map(([url]) => url);
    expect(urls).toEqual([
      "http://127.0.0.1:8000/api/v1/owner/seats/",
      "/api/v1/auth/refresh/",
      "http://127.0.0.1:8000/api/v1/owner/seats/",
    ]);
    const retryInit = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect((retryInit.headers as Record<string, string>).Authorization).toBe("Bearer fresh");
    expect(tokenStore.get()).toBe("fresh");
  });

  it("shares one refresh between concurrent requests", async () => {
    tokenStore.set("expired");
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => {
      if (url === "/api/v1/auth/refresh/") return ok({ access: "fresh" });
      const auth = (init.headers as Record<string, string>).Authorization;
      return auth === "Bearer fresh" ? ok({ url }) : unauthorized();
    });

    await Promise.all([api.get("/a/"), api.get("/b/"), api.get("/c/")]);

    const refreshCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/v1/auth/refresh/");
    expect(refreshCalls).toHaveLength(1);
  });

  it("signs out and reports session expiry when refresh fails", async () => {
    tokenStore.set("expired");
    const expired = vi.fn();
    onSessionExpired(expired);
    fetchMock.mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(unauthorized());

    await expect(api.get("/student/memberships/")).rejects.toMatchObject({ code: "TOKEN_INVALID" });
    expect(tokenStore.get()).toBeNull();
    expect(expired).toHaveBeenCalledOnce();
  });

  it("never refreshes for login failures", async () => {
    fetchMock.mockResolvedValueOnce(
      envelopeResponse(401, { success: false, error: "Wrong", error_code: "INVALID_CREDENTIALS" }),
    );
    await expect(request("/auth/login/", { method: "POST", body: {}, auth: false })).rejects.toMatchObject({
      code: "INVALID_CREDENTIALS",
    });
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
