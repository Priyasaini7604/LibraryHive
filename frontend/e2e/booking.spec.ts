import { type Page, expect, test } from "@playwright/test";

import { DEMO_LIBRARY_NAME, apiLogin, apiRegister, newAccount, stubCheckout, uiLogin, releaseE2eSeats } from "./helpers";

interface CheckoutOptions {
  key: string;
  order_id: string;
  amount: number;
}

/** Sign up a fresh student, open the demo library and hold a random free seat, ending on the checkout page. */
async function holdASeat(page: Page): Promise<{ email: string; password: string }> {
  const account = newAccount("student");
  await apiRegister(account);
  await uiLogin(page, account.email, account.password);
  await expect(page).toHaveURL(/\/student/);
  await page.goto("/discover");
  await page.getByText(DEMO_LIBRARY_NAME).first().click();
  const free = page.getByRole("button", { name: /^Seat .*, free$/ });
  await expect(free.first()).toBeVisible();
  const count = await free.count();
  await free.nth(Math.floor(Math.random() * count)).click();
  await page.getByRole("radio", { name: /Monthly/ }).click();
  await page.getByRole("button", { name: /^Hold seat / }).click();
  await expect(page).toHaveURL(/\/student\/book\/[0-9a-f-]{36}/);
  await expect(page.getByRole("heading", { name: "Complete your booking" })).toBeVisible();
  return account;
}

test.beforeAll(releaseE2eSeats);
test.afterAll(releaseE2eSeats);

test.describe("seat hold and checkout with the fake gateway (no request reaches Razorpay)", () => {
  test("a student holds a seat and pays: one membership, the fake gateway issued the order", async ({ page }) => {
    await stubCheckout(page, "success");
    const razorpayRequests: string[] = [];
    page.on("request", (request) => {
      if (/razorpay\.com/.test(request.url())) razorpayRequests.push(request.url());
    });
    await holdASeat(page);
    await page.getByRole("button", { name: /^Pay / }).click();
    await expect(page.getByText("Your seat is booked")).toBeVisible();
    await expect(page.getByText(/receipt LH-/)).toBeVisible();

    // The order came from the local fake gateway with dummy keys, never from Razorpay.
    const options = (await page.evaluate(() => (window as unknown as { __e2eOptions: CheckoutOptions }).__e2eOptions));
    expect(options.order_id).toMatch(/^order_e2e_[0-9a-f]{16}$/);
    expect(options.key).toBe("rzp_test_e2e_dummy");
    // Only the stubbed checkout script was requested from the Razorpay host, and it never reached the network.
    expect(razorpayRequests.every((url) => url.endsWith("/v1/checkout.js"))).toBe(true);

    await page.goto("/student/memberships");
    await expect(page.getByText(DEMO_LIBRARY_NAME).first()).toBeVisible();
  });

  test("a failed card shows a clear message, offers another try and creates no membership", async ({ page }) => {
    await stubCheckout(page, "failure");
    const account = await holdASeat(page);
    await page.getByRole("button", { name: /^Pay / }).click();
    await expect(page.getByText("The payment didn't go through")).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();

    const { api } = await apiLogin(account.email, account.password);
    const memberships = await api.get("/api/v1/student/memberships/");
    expect(((await memberships.json()) as { data: unknown[] }).data).toEqual([]);
    await api.dispose();
  });

  test("closing the payment window keeps the hold and creates no membership", async ({ page }) => {
    await stubCheckout(page, "dismiss");
    const account = await holdASeat(page);
    await page.getByRole("button", { name: /^Pay / }).click();
    await expect(page.getByText("Payment not completed")).toBeVisible();

    const { api } = await apiLogin(account.email, account.password);
    const memberships = await api.get("/api/v1/student/memberships/");
    expect(((await memberships.json()) as { data: unknown[] }).data).toEqual([]);
    const holds = await api.get("/api/v1/student/holds/current/");
    expect(holds.status()).toBe(200);
    await api.dispose();
  });

  test("a second student cannot take a seat that is already held (409), and cannot cancel someone else's hold (404)", async ({
    page,
  }) => {
    await stubCheckout(page, "dismiss");
    const first = await holdASeat(page);
    const holdId = /\/student\/book\/([0-9a-f-]{36})/.exec(page.url())?.[1] ?? "";
    const { api: firstApi } = await apiLogin(first.email, first.password);
    const mine = await firstApi.get("/api/v1/student/holds/current/");
    const hold = ((await mine.json()) as { data: { seat: { id: string }; plan: { id: string } }[] }).data[0];
    expect(hold).toBeDefined();

    const second = newAccount("student", "second");
    await apiRegister(second);
    const { api: secondApi } = await apiLogin(second.email, second.password);
    const taken = await secondApi.post("/api/v1/student/holds/", { data: { seat_id: hold?.seat.id, plan_id: hold?.plan.id } });
    expect(taken.status()).toBe(409);
    const cancel = await secondApi.post(`/api/v1/student/holds/${holdId}/cancel/`);
    expect(cancel.status()).toBe(404);
    await Promise.all([firstApi.dispose(), secondApi.dispose()]);
  });

  test("a signed-out visitor choosing a seat is sent to log in and comes back to the same library", async ({ page }) => {
    await page.goto("/discover");
    await page.getByText(DEMO_LIBRARY_NAME).first().click();
    await expect(page).toHaveURL(/\/libraries\/[0-9a-f-]{36}/);
    const libraryUrl = page.url();
    await page.getByRole("button", { name: /^Seat .*, free$/ }).first().click();
    await page.getByRole("link", { name: /^Log in to book seat/ }).click();
    await expect(page).toHaveURL(/\/login\?next=/);
    expect(decodeURIComponent(page.url())).toContain(new URL(libraryUrl).pathname);
  });
});
