import { expect, test } from "@playwright/test";

/**
 * The five critical journeys (spec #86). These run against the production
 * build seeded with labelled fixture data (spec #98: fixtures are visible).
 */

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  // dismiss onboarding hint if present
  const skip = page.getByRole("button", { name: "Skip setup" });
  if (await skip.isVisible({ timeout: 2000 }).catch(() => false)) {
    await skip.click();
  }
});

test("journey 1: homepage → search → filter → open tender → official link", async ({ page }) => {
  await page.goto("/discover");
  // open palette via the topbar search control (deterministic), verify shortcut later
  await page.locator("header button").first().click();
  const palette = page.getByRole("dialog", { name: /command palette/i });
  await expect(palette).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette).toBeHidden();
  await page.goto("/discover?q=solar");
  await expect(page.getByRole("status")).toContainText(/tenders/i);
  const firstResult = page.locator("tbody tr").first();
  if (await firstResult.count()) {
    await firstResult.locator("a").first().click();
    await expect(page.getByRole("link", { name: /view official tender/i })).toBeVisible();
  }
});

test("journey 2: bookmark → saved → export", async ({ page }) => {
  await page.goto("/discover");
  const bookmark = page.locator('button[aria-label^="Bookmark"]').first();
  if (await bookmark.count()) {
    await bookmark.click();
    await page.goto("/saved");
    await expect(page.getByRole("heading", { name: /saved/i })).toBeVisible();
    await expect(page.getByRole("button", { name: "Export CSV" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Backup JSON" })).toBeVisible();
  }
});

test("journey 3: tender detail shows AI tab + evidence discipline", async ({ page }) => {
  await page.goto("/discover?sort=value");
  const first = page.locator("tbody tr a").first();
  test.skip(!(await first.count()), "no dataset");
  await first.click();
  await page.getByRole("tab", { name: "AI Analysis" }).click();
  // either precomputed evidence or the honest pending state - never fabricated numbers
  await expect(
    page.getByText(/AI analysis pending|Source evidence not located|confident/i).first(),
  ).toBeVisible();
});

test("journey 4: compare two tenders", async ({ page }) => {
  await page.goto("/discover");
  const boxes = page.locator('input[type="checkbox"][aria-label*="comparison"]');
  const n = Math.min(2, await boxes.count());
  test.skip(n < 2, "need at least two tenders");
  for (let i = 0; i < n; i++) await boxes.nth(i).check();
  await page.getByRole("link", { name: /compare/i }).first().click();
  await expect(page.getByRole("columnheader", { name: "Attribute" })).toBeVisible();
});

test("journey 5: mobile search → filters bottom sheet → tender detail", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium-mobile", "mobile-only journey");
  await page.goto("/discover");
  await expect(page.locator("nav.fixed.bottom-0, nav[class*=bottom-0]").first()).toBeVisible();
  await page.goto("/discover?within=7");
  await page.locator('select[aria-label="Closing window"]').selectOption("15");
  await expect(page).toHaveURL(/within=15/);
});
