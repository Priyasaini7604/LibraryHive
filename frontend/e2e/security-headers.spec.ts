import { expect, test } from "@playwright/test";

import { DEMO_LIBRARY_NAME, watchCspViolations } from "./helpers";

/**
 * SECURITY.md section 20, "Headers": checked in a real browser against a production build (`next start`).
 * HSTS from the Django side needs HTTPS and a real host, so it cannot be proven here (see e2e/README.md).
 */
test.describe("security headers in a real browser", () => {
  test("pages carry a nonce-based CSP and the fixed security headers", async ({ request }) => {
    for (const path of ["/", "/discover", "/login"]) {
      const response = await request.get(path);
      expect(response.status(), path).toBe(200);
      const headers = response.headers();
      const csp = headers["content-security-policy"] ?? "";
      expect(csp, path).toMatch(/script-src[^;]*'nonce-[A-Za-z0-9+/=]+'/);
      expect(csp, path).toContain("'strict-dynamic'");
      expect(csp, path).not.toContain("'unsafe-eval'");
      expect(csp, path).toContain("object-src 'none'");
      expect(csp, path).toContain("base-uri 'self'");
      expect(headers["x-content-type-options"], path).toBe("nosniff");
      expect(headers["x-frame-options"], path).toBe("DENY");
      expect(headers["referrer-policy"], path).toBe("strict-origin-when-cross-origin");
      expect(headers["strict-transport-security"], path).toContain("max-age=");
      expect(headers["x-powered-by"], path).toBeUndefined();
    }
  });

  test("every request gets a fresh nonce", async ({ request }) => {
    const nonceOf = async () => {
      const csp = (await request.get("/login")).headers()["content-security-policy"] ?? "";
      return /'nonce-([^']+)'/.exec(csp)?.[1];
    };
    const [first, second] = [await nonceOf(), await nonceOf()];
    expect(first).toBeTruthy();
    expect(first).not.toBe(second);
  });

  test("the main public pages load without a single CSP violation or console error", async ({ page }) => {
    const violations = watchCspViolations(page);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/");
    await page.goto("/discover");
    await expect(page.getByText(DEMO_LIBRARY_NAME).first()).toBeVisible();
    await page.getByText(DEMO_LIBRARY_NAME).first().click();
    await expect(page.getByRole("heading", { level: 1, name: DEMO_LIBRARY_NAME })).toBeVisible();
    await page.goto("/login");
    await page.goto("/register");
    expect(violations).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("the backend adds its own hardening headers to API responses", async ({ request }) => {
    const response = await request.get("http://127.0.0.1:8010/api/v1/health/");
    expect(response.status()).toBe(200);
    const headers = response.headers();
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-request-id"]).toBeTruthy();
  });
});
