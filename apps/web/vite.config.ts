/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // GitHub Pages project sites live under /<repo>/; the deploy workflow sets BASE_PATH.
  base: process.env.BASE_PATH ?? "/",
  build: { target: "es2020" },
  test: {
    // e2e/ holds Playwright specs, run separately via `npm run e2e`
    include: ["src/**/*.test.ts"],
  },
});
