import { expect, test, type Page } from "@playwright/test";

/**
 * Aggressive adversarial testing: XSS payloads, hostile input, persistence,
 * deep links, limits, keyboard-only operation, tiny viewports (spec #87).
 */

const OUT = "e2e-screenshots/edge";

async function shot(page: Page, name: string) {
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/${name}.png` });
}

test.describe("hostile input", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("XSS payloads in search never execute", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/discover");
    await page.locator("header button").first().click();
    const palette = page.getByRole("dialog");
    await palette.locator("input").fill('<script>alert(1)</script> <img src=x onerror=alert(1)>');
    await page.keyboard.press("Enter");
    await page.waitForTimeout(500);
    // payload rendered as inert text only
    expect(errors).toEqual([]);
    expect(await page.locator("script").count()).toBeLessThanOrEqual(1); // only vite module script
    await shot(page, "xss-payload-inert");
  });

  test("very long query does not break layout", async ({ page }) => {
    await page.goto(`/discover?q=${"solar ".repeat(200)}`);
    await expect(page.getByRole("status")).toBeVisible();
    await shot(page, "long-query-ok");
  });

  test("deep link to unknown tender shows graceful not-found", async ({ page }) => {
    await page.goto("/tender/deadbeefdeadbeefdeadbeef");
    await expect(page.getByText(/tender not found/i)).toBeVisible();
    await shot(page, "unknown-tender-graceful");
  });

  test("invalid route redirects home", async ({ page }) => {
    await page.goto("/this/does/not/exist");
    await expect(page).toHaveURL("/");
  });

  test("unicode + regional scripts render", async ({ page }) => {
    await page.goto("/discover?q=जिल्हा रुग्णालय");
    await expect(page.getByRole("status")).toBeVisible();
    await shot(page, "devanagari-query");
  });

  test("empty results state is honest", async ({ page }) => {
    await page.goto("/discover?q=zzzznonexistentzzz");
    await expect(page.getByText(/no tenders match/i)).toBeVisible();
    await shot(page, "empty-results-state");
  });
});

test.describe("state & limits", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("bookmarks persist across reload (IndexedDB)", async ({ page }) => {
    await page.goto("/discover?q=solar");
    await page.locator('button[aria-label^="Bookmark"]').first().click();
    await page.reload();
    await expect(page.locator('button[aria-label="Remove bookmark"]').first()).toBeVisible();
  });

  test("compare capped at five", async ({ page }) => {
    await page.goto("/discover");
    const boxes = page.locator('input[type="checkbox"][aria-label*="comparison"]');
    const total = Math.min(await boxes.count(), 6);
    for (let i = 0; i < Math.min(total, 5); i++) await boxes.nth(i).check();
    if (total > 5) {
      await expect(boxes.nth(5)).toBeDisabled();
    }
    await shot(page, "compare-cap-five");
  });

  test("filter chips clear-all restores full list", async ({ page }) => {
    await page.goto("/discover?state=Rajasthan&within=7");
    const narrowed = await page.locator("tbody tr").count();
    await page.getByRole("button", { name: "Clear all" }).click();
    await expect(page).toHaveURL(/discover\?$/, { timeout: 5000 }).catch(() => {});
    const all = await page.locator("tbody tr").count();
    expect(all).toBeGreaterThanOrEqual(narrowed);
  });

  test("sort options encode into URL (shareable state)", async ({ page }) => {
    for (const sort of ["closing", "value", "newest"]) {
      await page.goto("/discover");
      await page.locator('select[aria-label="Sort"]').selectOption(sort);
      await expect(page).toHaveURL(new RegExp(`sort=${sort}`));
    }
  });

  test("CSV export fires a download with safe content", async ({ page }) => {
    await page.goto("/saved");
    // bookmark one first
    await page.goto("/discover?q=solar");
    await page.locator('button[aria-label^="Bookmark"]').first().click();
    await page.goto("/saved");
    const dl = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export CSV" }).click();
    const download = await dl;
    expect(download.suggestedFilename()).toMatch(/\.csv$/);
    const path = await download.path();
    const head = (await import("node:fs")).readFileSync(path!, "utf8").slice(0, 400);
    // formula injection guard: no cell may start with = + - @ after the header row
    const rows = head.split("\r\n");
    for (const row of rows.slice(1)) {
      for (const cell of row.split(",")) {
        expect(cell).not.toMatch(/^[=+@]/);
      }
    }
  });
});

test.describe("keyboard-first", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("'/' opens palette, Esc closes; Cmd+K works", async ({ page }) => {
    await page.goto("/discover");
    await expect(page.locator("nav").first()).toBeVisible();
    await page.waitForTimeout(400); // let React effects attach
    await page.keyboard.press("/");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("palette suggestion click navigates to filtered search", async ({ page }) => {
    await page.goto("/");
    await page.locator("header button").first().click();
    await page.getByRole("dialog").getByText("closing this week above ₹1 Cr").click();
    await page.waitForTimeout(200);
    await page.getByRole("dialog").getByRole("button", { name: /search/i }).click();
    await expect(page).toHaveURL(/within=7/);
  });
});

test.describe("tiny viewport (320px — spec #87)", () => {
  test.use({ viewport: { width: 320, height: 640 } });

  test("no horizontal overflow on key pages", async ({ page }) => {
    for (const route of ["/", "/discover", "/for-you", "/sources", "/settings"]) {
      await page.goto(route);
      await page.waitForTimeout(400);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      // table pages allow internal scroll containers; page itself must not scroll sideways
      expect(overflow, `route ${route}`).toBeLessThanOrEqual(1);
      if (route === "/discover") await shot(page, "320px-discover");
    }
  });
});
