import { expect, test, type Page } from "@playwright/test";

/**
 * Guided walkthrough (spec #100 final product test): captures a screenshot at
 * every user-facing step so a new user can follow along visually.
 * Output: apps/web/e2e-screenshots/*.png
 */

const OUT = "e2e-screenshots";

async function shot(page: Page, name: string) {
  await page.waitForTimeout(350); // let transitions settle
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });
}

async function dismissOnboarding(page: Page) {
  await page.goto("/");
  const skip = page.getByRole("button", { name: "Skip setup" });
  if (await skip.isVisible({ timeout: 2500 }).catch(() => false)) await skip.click();
}

test.describe.serial("guided tour — desktop 1280x800", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("01 landing and briefing", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /today’s briefing/i })).toBeVisible();
    await shot(page, "01-home-briefing");
  });

  test("02 global search with interpreted filters", async ({ page }) => {
    await page.goto("/");
    await page.locator("header button").first().click();
    const palette = page.getByRole("dialog");
    await expect(palette).toBeVisible();
    await palette.locator("input").fill("solar EPC Maharashtra above ₹1 Cr closing within 30 days");
    await page.waitForTimeout(400);
    await shot(page, "02-command-palette-nlq");
    // interpreted filter chips visible -> run the search
    await palette.getByRole("button", { name: /search/i }).click();
    await expect(page.getByRole("status")).toContainText(/tenders/i);
    await shot(page, "03-discover-search-results");
  });

  test("04 filters progressive disclosure + chips", async ({ page }) => {
    await page.goto("/discover?state=Maharashtra&within=30&min=10000000");
    await expect(page.getByRole("status")).toBeVisible();
    await shot(page, "04-filters-active-chips");
    await page.getByRole("button", { name: "More filters" }).click();
    await page.waitForTimeout(300);
    await shot(page, "05-more-filters-expanded");
  });

  test("06 sorting and card view", async ({ page }) => {
    await page.goto("/discover");
    await page.locator('select[aria-label="Sort"]').selectOption("value");
    await expect(page).toHaveURL(/sort=value/);
    await page.locator('div[role="group"] button').nth(1).click(); // cards view
    await page.waitForTimeout(300);
    await shot(page, "06-card-view-sorted-value");
  });

  test("07-11 tender detail tabs", async ({ page }) => {
    // open the solar tender which carries AI fixtures
    await page.goto("/discover?q=solar");
    const link = page.locator("tbody tr").filter({ hasText: /solar photovoltaic/i }).locator("a").first();
    await link.click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/solar/i);
    await shot(page, "07-tender-hero");

    for (const [tab, file] of [
      ["Eligibility", "08-tab-eligibility"],
      ["Documents", "09-tab-documents"],
      ["Corrigenda", "10-tab-corrigenda"],
      ["Timeline", "11-tab-timeline"],
      ["AI Analysis", "12-tab-ai-analysis"],
    ] as const) {
      await page.getByRole("tab", { name: new RegExp(tab.replace(" ", "\\s*"), "i") }).click();
      await shot(page, file);
    }
    // similar opportunities live below the fold
    await page.mouse.wheel(0, 1200);
    await shot(page, "13-similar-opportunities");
  });

  test("14 bookmark then saved workspace", async ({ page }) => {
    await page.goto("/discover?q=solar");
    await page.locator('button[aria-label^="Bookmark"]').first().click();
    await page.goto("/saved");
    await expect(page.getByText(/bookmarked tenders/i)).toBeVisible();
    await shot(page, "14-saved-workspace");
  });

  test("15 compare two tenders", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "chromium-desktop", "checkbox matrix is desktop UX");
    await page.goto("/discover");
    const boxes = page.locator('input[type="checkbox"][aria-label*="comparison"]');
    await expect(boxes.first()).toBeVisible();
    await boxes.nth(0).click();
    await boxes.nth(1).click();
    await shot(page, "15-compare-bar");
    await page.getByRole("link", { name: /compare \(/i }).first().click();
    await expect(page.getByRole("rowheader", { name: "Value" })).toBeVisible();
    await expect(page.getByRole("rowheader", { name: "Deadline" })).toBeVisible();
    await shot(page, "16-compare-matrix");
  });

  test("17 for-you profile setup", async ({ page }) => {
    await page.goto("/for-you");
    await shot(page, "17-foryou-profile-form");
    await page.locator("input").first().fill("solar, roads");
    await page.getByRole("button", { name: /save profile/i }).click();
    await page.waitForTimeout(500);
    await shot(page, "18-foryou-ranked");
  });

  test("19 settings privacy modes", async ({ page }) => {
    await page.goto("/settings");
    await shot(page, "19-settings-privacy-byok");
  });

  test("20 copilot without key (BYOK gate)", async ({ page }) => {
    await page.goto("/discover?q=solar");
    await page.locator("tbody tr a").first().click();
    await page.getByRole("button", { name: /ask ai about this tender/i }).click();
    await expect(page.getByRole("complementary", { name: /tender copilot/i })).toBeVisible();
    await shot(page, "20-copilot-byok-gate");
  });

  test("21 sources health dashboard", async ({ page }) => {
    await page.goto("/sources");
    await expect(page.getByRole("heading", { name: /sources & system health/i })).toBeVisible();
    await shot(page, "21-sources-health");
  });

  test("22 calendar export downloads .ics", async ({ page }) => {
    await page.goto("/discover?q=solar");
    await page.locator("tbody tr a").first().click();
    const dl = page.waitForEvent("download");
    await page.getByRole("button", { name: "Add to calendar" }).click();
    const download = await dl;
    expect(download.suggestedFilename()).toMatch(/\.ics$/);
  });
});

test.describe.serial("mobile 375x812", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("16b mobile compare via detail button", async ({ page }) => {
    await page.goto("/discover?q=solar");
    await page.locator("article a").first().click();
    await page.getByRole("button", { name: /^Compare$/ }).click();
    await expect(page.getByRole("link", { name: /compare \(/i })).toBeVisible();
    await shot(page, "26b-mobile-compare-selected");
  });

  test("23 mobile home + bottom nav", async ({ page }) => {
    await dismissOnboarding(page);
    await shot(page, "23-mobile-home");
  });

  test("24 mobile discover cards", async ({ page }) => {
    await page.goto("/discover?q=solar");
    await page.waitForTimeout(600);
    await shot(page, "24-mobile-discover-cards");
  });

  test("25 mobile tender detail with sticky bar", async ({ page }) => {
    await page.goto("/discover?q=solar");
    await page.locator("article a, tbody a").first().click();
    await page.waitForTimeout(600);
    await shot(page, "25-mobile-tender-sticky-bar");
    await page.mouse.wheel(0, 1500);
    await shot(page, "26-mobile-sticky-action-bar");
  });
});
