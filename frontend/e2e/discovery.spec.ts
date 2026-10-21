import { expect, test } from "@playwright/test";

import { DEMO_LIBRARY_NAME } from "./helpers";

test.describe("library discovery and the public library page", () => {
  test("the discover page lists the demo library from the real API and opens its page", async ({ page }) => {
    await page.goto("/discover");
    const card = page.getByText(DEMO_LIBRARY_NAME).first();
    await expect(card).toBeVisible();
    await card.click();
    await expect(page).toHaveURL(/\/libraries\/[0-9a-f-]{36}/);
    await expect(page.getByRole("heading", { level: 1, name: DEMO_LIBRARY_NAME })).toBeVisible();
  });

  test("the library page shows plans, a live seat map and who studies here", async ({ page }) => {
    await page.goto("/discover");
    await page.getByText(DEMO_LIBRARY_NAME).first().click();
    const plans = page.getByRole("region", { name: "Plans" });
    await expect(plans.getByText("Monthly")).toBeVisible();
    await expect(page.getByRole("button", { name: /^Seat A-1, / })).toBeVisible();
    const who = page.getByRole("region", { name: "Who studies here" });
    await expect(who.getByRole("list", { name: "Members by exam" })).toBeVisible(); // domain_breakdown (#15)
  });

  test("searching for a name nobody has shows the empty state, and it can be cleared", async ({ page }) => {
    await page.goto("/discover?search=zzzz-no-such-library");
    await expect(page.getByText(/no libraries found/i)).toBeVisible();
    await page.getByRole("button", { name: /clear filters/i }).click();
    await expect(page.getByText(DEMO_LIBRARY_NAME).first()).toBeVisible();
  });

  test("an unknown library id explains itself instead of crashing", async ({ page }) => {
    await page.goto("/libraries/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText("This library isn't available")).toBeVisible();
  });
});
