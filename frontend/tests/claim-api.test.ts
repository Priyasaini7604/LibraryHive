import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { completeClaim, startClaim } from "@/lib/api/auth";
import { tokenStore } from "@/lib/auth";
import { ApiError } from "@/lib/errors";

function envelope(status: number, body: Record<string, unknown>): Response {
  return new Response(
    JSON.stringify({ data: null, error: null, error_code: null, details: null, request_id: "req-1", ...body }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  tokenStore.clear();
});

afterEach(() => vi.unstubAllGlobals());

describe("account claim client (#12, #13)", () => {
  it("starts a claim through the same-origin auth proxy without a session", async () => {
    fetchMock.mockResolvedValueOnce(
      envelope(200, { success: true, data: { channel: "email_otp", masked_email: null } }),
    );

    await expect(startClaim({ phone: "98111 00050", channel: "email_otp" })).resolves.toEqual({
      channel: "email_otp",
      masked_email: null,
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/claim/start/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ phone: "98111 00050", channel: "email_otp" });
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("completing a claim keeps the access token in memory and returns the user", async () => {
    const user = { id: "u1", name: "Rahul Sharma", email: "rahul@example.com", role: "student" };
    fetchMock.mockResolvedValueOnce(envelope(200, { success: true, data: { access: "jwt-access", user } }));

    await expect(completeClaim({ phone: "9811100050", code: "123456", password: "Brand-new-Pass-987" })).resolves.toEqual(
      user,
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/claim/complete/");
    expect(JSON.parse(init.body as string)).toEqual({
      phone: "9811100050",
      code: "123456",
      password: "Brand-new-Pass-987",
    });
    expect(tokenStore.get()).toBe("jwt-access");
  });

  it("surfaces the backend error code for a wrong code and stores no session", async () => {
    fetchMock.mockResolvedValueOnce(
      envelope(400, { success: false, error: "That code is wrong or has expired.", error_code: "CLAIM_INVALID" }),
    );

    const error = (await completeClaim({ phone: "9811100050", code: "000000", password: "x" }).catch(
      (e: unknown) => e,
    )) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("CLAIM_INVALID");
    expect(tokenStore.get()).toBeNull();
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
