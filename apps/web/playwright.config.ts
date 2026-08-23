import { defineConfig } from "@playwright/test";

/**
 * E2E journeys (spec #86). Run locally with:
 *   npx playwright install chromium
 *   npm run seed && npm run build
 *   npx playwright test
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://localhost:4300",
    screenshot: "only-on-failure",
  },
  webServer: {
    // strictPort + no-reuse guarantees we NEVER test against a stale/foreign server
    command: "npm run preview -- --port 4300 --strictPort",
    port: 4300,
    reuseExistingServer: false,
    stdout: "ignore",
    stderr: "pipe",
  },
  projects: [
    { name: "chromium-desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "chromium-mobile", use: { viewport: { width: 375, height: 812 } } },
  ],
});
