import { createHmac, randomBytes } from "node:crypto";

import { type APIRequestContext, type Page, expect, request as playwrightRequest } from "@playwright/test";

export const FRONTEND = "http://127.0.0.1:3010";
export const BACKEND_API = "http://127.0.0.1:8010/api/v1";

/** Published on purpose by the seed_demo command (demo data only). */
export const DEMO_PASSWORD = "Demo-pass-12345";
export const DEMO_OWNER_EMAIL = "owner@demo.libraryhive.test";
export const DEMO_LIBRARY_NAME = "Demo Study Hall";

/** The dummy secret in config/settings/e2e.py; the fake checkout signs with it so real HMAC code verifies. */
export const E2E_KEY_SECRET = "e2e-dummy-key-secret";

export interface Account {
  email: string;
  phone: string;
  name: string;
  password: string;
  role: "student" | "owner";
}

let counter = 0;

/** A unique, valid account so tests never collide on the shared database. */
export function newAccount(role: Account["role"], label: string = role): Account {
  counter += 1;
  const stamp = `${Date.now().toString(36)}${randomBytes(2).toString("hex")}${counter}`;
  // Indian mobile numbers start with 6-9: 9 + 9 digits from the stamp's decimal digits.
  const digits = `${Date.now()}${counter}`.replace(/\D/g, "").slice(-9).padStart(9, "1");
  return {
    email: `${label}.${stamp}@e2e.libraryhive.test`,
    phone: `9${digits}`,
    name: `E2E ${label} ${stamp}`,
    password: "E2e-pass-98765!",
    role,
  };
}

interface Session {
  api: APIRequestContext;
  token: string;
}

/** Sign in through the frontend's same-site auth proxy (the same route the browser uses). */
export async function apiLogin(email: string, password: string): Promise<Session> {
  const auth = await playwrightRequest.newContext({ baseURL: FRONTEND, extraHTTPHeaders: { Origin: FRONTEND } });
  const response = await auth.post("/api/v1/auth/login/", { data: { email, password } });
  expect(response.status(), await response.text()).toBe(200);
  const body = (await response.json()) as { data: { access: string } };
  await auth.dispose();
  const api = await playwrightRequest.newContext({
    baseURL: BACKEND_API.replace(/\/api\/v1$/, ""),
    extraHTTPHeaders: { Authorization: `Bearer ${body.data.access}` },
  });
  return { api, token: body.data.access };
}

export async function apiRegister(account: Account): Promise<void> {
  const auth = await playwrightRequest.newContext({ baseURL: FRONTEND, extraHTTPHeaders: { Origin: FRONTEND } });
  const response = await auth.post("/api/v1/auth/register/", {
    data: { role: account.role, name: account.name, email: account.email, phone: account.phone, password: account.password },
  });
  expect(response.status(), await response.text()).toBe(201);
  await auth.dispose();
}

export async function uiLogin(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
}

export async function uiLogout(page: Page): Promise<void> {
  await page.getByRole("button", { name: /log out|sign out/i }).first().click();
}

/** Replace Razorpay's hosted checkout with a local stub; no request ever reaches Razorpay. */
export async function stubCheckout(page: Page, outcome: "success" | "failure" | "dismiss"): Promise<void> {
  await page.route("https://checkout.razorpay.com/**", async (route) => {
    await route.fulfill({
      contentType: "application/javascript",
      body: `
        window.Razorpay = function (options) {
          this.options = options;
          window.__e2eOptions = options;
          this.handlers = {};
        };
        window.Razorpay.prototype.on = function (event, handler) { this.handlers[event] = handler; };
        window.Razorpay.prototype.open = function () {
          var self = this;
          setTimeout(function () {
            var outcome = ${JSON.stringify(outcome)};
            if (outcome === "success") {
              window.__e2eSign(self.options.order_id).then(function (paymentId) {
                window.__e2eSignature(self.options.order_id, paymentId).then(function (signature) {
                  self.options.handler({
                    razorpay_order_id: self.options.order_id,
                    razorpay_payment_id: paymentId,
                    razorpay_signature: signature,
                  });
                });
              });
            } else if (outcome === "failure") {
              self.handlers["payment.failed"]({ error: { description: "Card declined (e2e stub)" } });
            } else {
              self.options.modal.ondismiss();
            }
          }, 50);
        };
      `,
    });
  });
  // HMAC runs in Node (the test), never in the page: the secret stays out of the browser.
  await page.exposeFunction("__e2eSign", (orderId: string) => `pay_e2e_${orderId.slice(-6)}_${randomBytes(3).toString("hex")}`);
  await page.exposeFunction("__e2eSignature", (orderId: string, paymentId: string) =>
    createHmac("sha256", E2E_KEY_SECRET).update(`${orderId}|${paymentId}`).digest("hex"),
  );
}

/** Collect Content-Security-Policy violations reported by the browser while a test runs. */
export function watchCspViolations(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (message) => {
    const text = message.text();
    if (/content security policy|refused to (load|execute|connect|apply)/i.test(text)) violations.push(text);
  });
  return violations;
}

/**
 * Give back the seats this suite used. Bookings and admissions take seats for real, so without this the demo
 * library fills up after a few runs. Only members and holds whose student name starts with "E2E " (created by
 * `newAccount`) are touched, through the owner's own endpoints, so demo data and real data are never affected.
 */
export async function releaseE2eSeats(): Promise<void> {
  const { api } = await apiLogin(DEMO_OWNER_EMAIL, DEMO_PASSWORD);
  const members = await api.get("/api/v1/owner/members/?page_size=100");
  const rows = ((await members.json()) as { data: { items: { membership_id: string; student: { name: string } }[] } }).data.items;
  for (const row of rows.filter((member) => member.student.name.startsWith("E2E "))) {
    const archived = await api.post(`/api/v1/owner/members/${row.membership_id}/archive/`, {
      data: { reason: "End-to-end test cleanup" },
    });
    expect(archived.status(), await archived.text()).toBe(200);
  }
  const seats = await api.get("/api/v1/owner/seats/");
  const list = ((await seats.json()) as { data: { seats: { hold: { id: string; kind: string; student_name?: string } | null }[] } }).data.seats;
  for (const seat of list) {
    if (seat.hold?.kind === "booking" && seat.hold.student_name?.startsWith("E2E ")) {
      const released = await api.post(`/api/v1/owner/holds/${seat.hold.id}/release/`, {
        data: { reason: "End-to-end test cleanup" },
      });
      expect([200, 409]).toContain(released.status()); // 409: it expired or was paid meanwhile
    }
  }
  await api.dispose();
}
