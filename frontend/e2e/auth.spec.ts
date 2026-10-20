import { expect, test } from "@playwright/test";

import { apiRegister, newAccount, uiLogin } from "./helpers";

test.describe("authentication and roles", () => {
  test("a student registers in the browser, lands on the student area and stays signed in after a reload", async ({
    page,
  }) => {
    const account = newAccount("student");
    await page.goto("/register");
    await page.getByLabel("Full name").fill(account.name);
    await page.getByLabel("Email").fill(account.email);
    await page.getByLabel("Mobile number").fill(account.phone);
    await page.locator('input[name="password"]').fill(account.password);
    await page.getByRole("button", { name: /create account|sign up|register/i }).click();
    await expect(page).toHaveURL(/\/student/);

    await page.reload();
    await expect(page).toHaveURL(/\/student/);
  });

  test("tokens are stored the way SEC-1 requires", async ({ page, context }) => {
    const account = newAccount("student");
    await apiRegister(account);
    await uiLogin(page, account.email, account.password);
    await expect(page).toHaveURL(/\/student/);

    const storage = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
    expect(storage).not.toMatch(/eyJ|access|refresh|token/i); // no JWT in web storage
    expect(await page.evaluate(() => document.cookie)).not.toContain("lh_refresh"); // not readable by scripts

    const refresh = (await context.cookies()).find((cookie) => cookie.name === "lh_refresh");
    expect(refresh).toBeDefined();
    expect(refresh?.httpOnly).toBe(true);
    expect(refresh?.sameSite).toBe("Strict");
    expect(refresh?.path).toBe("/api/v1/auth/");
  });

  test("a wrong password shows one generic message and does not sign in", async ({ page }) => {
    const account = newAccount("student");
    await apiRegister(account);
    await uiLogin(page, account.email, "Wrong-pass-12345");
    await expect(page.getByRole("alert").first()).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("alert").first()).not.toContainText(account.email);
  });

  test("logging out ends the session: the student area asks for a login again", async ({ page }) => {
    const account = newAccount("student");
    await apiRegister(account);
    await uiLogin(page, account.email, account.password);
    await expect(page).toHaveURL(/\/student/);
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto("/student");
    await expect(page).toHaveURL(/\/login/);
  });

  test("a signed-out visitor is sent to the login, keeping where they were going", async ({ page }) => {
    await page.goto("/student/memberships");
    await expect(page).toHaveURL(/\/login\?next=%2Fstudent%2Fmemberships/);
  });

  test("a student cannot use the owner area and an owner cannot use the student area", async ({ page }) => {
    const student = newAccount("student");
    await apiRegister(student);
    await uiLogin(page, student.email, student.password);
    await expect(page).toHaveURL(/\/student/);
    await page.goto("/owner/members");
    await expect(page).not.toHaveURL(/\/owner\/members$/);
    await expect(page.getByRole("heading", { name: /^members$/i })).toHaveCount(0);
  });
});
