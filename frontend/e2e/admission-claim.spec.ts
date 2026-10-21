import { type Page, expect, test } from "@playwright/test";

import { DEMO_LIBRARY_NAME, DEMO_OWNER_EMAIL, DEMO_PASSWORD, apiLogin, newAccount, uiLogin, releaseE2eSeats } from "./helpers";

/** Walk-in admission by the owner (cash), then the student claims the same account with the owner's code. */
async function admitWalkIn(page: Page, student: { name: string; phone: string }): Promise<string> {
  await uiLogin(page, DEMO_OWNER_EMAIL, DEMO_PASSWORD);
  await expect(page).toHaveURL(/\/owner/);
  await page.goto("/owner/members/new");
  await page.getByLabel("Full name").fill(student.name);
  await page.getByLabel("Mobile number").fill(student.phone);
  await page.getByRole("button", { name: "Check if they already have an account" }).click();
  await expect(page.getByText(/no account uses this phone number/i)).toBeVisible();

  const choices = page.getByRole("combobox");
  await choices.nth(1).click(); // Seat (index 0 is the optional exam)
  await page.getByRole("option").last().click();
  await choices.nth(2).click(); // Plan
  await page.getByRole("option", { name: /Monthly/ }).click();

  await page.getByRole("button", { name: "Admit student and record payment" }).click();
  await expect(page.getByRole("heading", { name: `${student.name} is admitted` })).toBeVisible();
  await expect(page.getByText(/receipt LH-/)).toBeVisible();

  await page.getByRole("button", { name: "Give a claim code" }).click();
  await page.getByRole("button", { name: "Create a claim code" }).click();
  const code = (await page.locator('p[aria-label="Claim code"]').textContent())?.trim() ?? "";
  expect(code.length).toBeGreaterThanOrEqual(8);
  await page.getByRole("button", { name: "Done" }).click();
  return code;
}

test.beforeAll(releaseE2eSeats);
test.afterAll(releaseE2eSeats);

test.describe("owner admission and student account claim", () => {
  test("a walk-in student is admitted with cash, then claims the same account with the owner's code", async ({
    page,
    browser,
  }) => {
    const walkIn = newAccount("student", "walkin");
    const code = await admitWalkIn(page, walkIn);

    // The student, in a separate browser session, claims the account by phone and owner code.
    const studentPage = await (await browser.newContext()).newPage();
    await studentPage.goto("/claim");
    await studentPage.getByLabel("Mobile number").fill(walkIn.phone);
    await studentPage.getByRole("radio", { name: /I have a code from my library/ }).click();
    await studentPage.getByRole("button", { name: "Continue" }).click();
    await studentPage.getByLabel("Library code").fill(code);
    await studentPage.locator('input[name="password"]').fill(walkIn.password);
    await studentPage.getByLabel("Email").fill(walkIn.email);
    await studentPage.getByRole("button", { name: "Link my account" }).click();
    await expect(studentPage).toHaveURL(/\/student\/memberships/);
    await expect(studentPage.getByText(DEMO_LIBRARY_NAME).first()).toBeVisible();

    // Same account, history intact: the cash payment made at admission is still on it, and the code is spent.
    const { api } = await apiLogin(walkIn.email, walkIn.password);
    const payments = await api.get("/api/v1/student/payments/");
    expect(payments.status()).toBe(200);
    const body = (await payments.json()) as { data: { items?: { method: string; status: string }[] } | { method: string; status: string }[] };
    const rows = Array.isArray(body.data) ? body.data : (body.data.items ?? []);
    expect(rows.some((row) => row.method === "cash" && row.status === "success")).toBe(true);
    await api.dispose();

    const again = await (await browser.newContext()).newPage();
    await again.goto("/claim");
    await again.getByLabel("Mobile number").fill(walkIn.phone);
    await again.getByRole("radio", { name: /I have a code from my library/ }).click();
    await again.getByRole("button", { name: "Continue" }).click();
    await again.getByLabel("Library code").fill(code);
    await again.locator('input[name="password"]').fill("Another-pass-12345!");
    await again.getByRole("button", { name: "Link my account" }).click();
    await expect(again.getByRole("alert").first()).toBeVisible(); // a used code is refused
    await expect(again).toHaveURL(/\/claim/);
  });

  test("a wrong claim code is refused with a message and signs nobody in", async ({ page, browser }) => {
    const walkIn = newAccount("student", "walkin2");
    await admitWalkIn(page, walkIn);
    const studentPage = await (await browser.newContext()).newPage();
    await studentPage.goto("/claim");
    await studentPage.getByLabel("Mobile number").fill(walkIn.phone);
    await studentPage.getByRole("radio", { name: /I have a code from my library/ }).click();
    await studentPage.getByRole("button", { name: "Continue" }).click();
    await studentPage.getByLabel("Library code").fill("WRONGCODE");
    await studentPage.locator('input[name="password"]').fill(walkIn.password);
    await studentPage.getByLabel("Email").fill(walkIn.email);
    await studentPage.getByRole("button", { name: "Link my account" }).click();
    await expect(studentPage.getByRole("alert").first()).toBeVisible();
    await expect(studentPage).toHaveURL(/\/claim/);
  });

  test("admitting the same phone number twice is refused: no second membership in that library", async ({ page }) => {
    const walkIn = newAccount("student", "dup");
    await admitWalkIn(page, walkIn);
    await page.getByRole("button", { name: "Admit another student" }).click();
    await page.getByLabel("Full name").fill(walkIn.name);
    await page.getByLabel("Mobile number").fill(walkIn.phone);
    await page.getByRole("button", { name: "Check if they already have an account" }).click();
    await expect(page.getByText("Already a member here")).toBeVisible();
    await expect(page.getByRole("button", { name: "Admit student and record payment" })).toBeDisabled();
  });
});
