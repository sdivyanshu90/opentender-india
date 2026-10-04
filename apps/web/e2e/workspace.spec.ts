import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  const skip = page.getByRole("button", { name: "Skip setup" });
  if (await skip.isVisible({ timeout: 2000 }).catch(() => false)) await skip.click();
});

test("home shows real stats and a feeds link", async ({ page }) => {
  await expect(page.getByTestId("home-stats")).toContainText(/active tenders/i);
  await expect(page.getByRole("link", { name: /atom feeds|subscribe/i }).first()).toBeVisible();
});

test("save a search, run it from Saved, delete it", async ({ page }) => {
  await page.goto("/discover?q=solar&sort=closing");
  await page.getByRole("button", { name: "Save this search" }).click();
  await page.getByLabel("Saved search name").fill("Solar closing");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.goto("/saved");
  await expect(page.getByText("Solar closing")).toBeVisible();
  await page.getByRole("link", { name: "Run saved search Solar closing" }).click();
  await expect(page).toHaveURL(/q=solar/);
  await page.goto("/saved");
  await page.getByRole("button", { name: "Delete saved search Solar closing" }).click();
  await expect(page.getByText("Solar closing")).toHaveCount(0);
});

test("export current results as CSV and JSON", async ({ page }) => {
  await page.goto("/discover");
  await expect(page.getByRole("status")).toContainText(/tenders/i);
  const [csv] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export CSV" }).click()]);
  const text = await readFile((await csv.path())!, "utf8");
  expect(text).toContain("tender_number");
  const [json] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export JSON" }).click()]);
  const rows = JSON.parse(await readFile((await json.path())!, "utf8"));
  expect(Array.isArray(rows)).toBe(true);
});

test("restore from backup merges valid data and rejects junk", async ({ page }) => {
  await page.goto("/settings");
  const input = page.getByLabel("Backup file");
  await input.setInputFiles({ name: "bad.json", mimeType: "application/json", buffer: Buffer.from("{nope") });
  await expect(page.getByText(/not a valid json/i)).toBeVisible();
  const good = { bookmarks: {}, savedSearches: [{ id: "r1", name: "Restored one", query: "q=road" }], profile: null };
  await input.setInputFiles({ name: "ok.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(good)) });
  await expect(page.getByText(/Restored 0 bookmarks and 1 saved/)).toBeVisible();
  await page.goto("/saved");
  await expect(page.getByText("Restored one")).toBeVisible();
});

test("tender detail shows last checked and a prefilled issue link", async ({ page }) => {
  await page.goto("/discover");
  await page.locator("main a[href*=\"/tender/\"]").first().click();
  await expect(page.getByText("Last checked")).toBeVisible();
  const href = await page.getByRole("link", { name: /report data issue/i }).getAttribute("href");
  expect(href).toContain("github.com/sdivyanshu90/opentender-india/issues/new");
  expect(href).toContain("title=");
});
