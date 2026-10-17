import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { confirmPasswordReset, requestPasswordReset } from "@/lib/api/auth";
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

describe("password reset client (#13a, #13b)", () => {
  it("requests a code through the same-origin auth proxy without credentials in the body", async () => {
    fetchMock.mockResolvedValueOnce(envelope(200, { success: true, data: { message: "sent" } }));

    await expect(requestPasswordReset("asha@example.com")).resolves.toEqual({ message: "sent" });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/password-reset/request/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ email: "asha@example.com" });
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("sends the new password under the API's snake_case name", async () => {
    fetchMock.mockResolvedValueOnce(envelope(200, { success: true, data: { message: "done" } }));

    await confirmPasswordReset({ email: "asha@example.com", code: "123456", newPassword: "Brand-new-Pass-987" });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/password-reset/confirm/");
    expect(JSON.parse(init.body as string)).toEqual({
      email: "asha@example.com",
      code: "123456",
      new_password: "Brand-new-Pass-987",
    });
  });

  it("never stores a session after a reset", async () => {
    fetchMock.mockResolvedValueOnce(envelope(200, { success: true, data: { message: "done" } }));
    await confirmPasswordReset({ email: "a@b.com", code: "123456", newPassword: "x" });
    expect(tokenStore.get()).toBeNull();
  });

  it("surfaces the backend error code for a wrong code and does not try to refresh a session", async () => {
    fetchMock.mockResolvedValueOnce(
      envelope(400, { success: false, error: "That code is wrong or has expired.", error_code: "RESET_INVALID" }),
    );

    const error = (await confirmPasswordReset({ email: "a@b.com", code: "000000", newPassword: "x" }).catch(
      (e: unknown) => e,
    )) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("RESET_INVALID");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
