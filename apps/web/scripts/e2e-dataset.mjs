#!/usr/bin/env node
/**
 * E2E only: production builds never fall back to fixtures (spec #52), so the
 * Playwright server needs a dataset in dist/. Package the labelled synthetic
 * fixtures (npm run seed) as data/index/search-docs.json.gz. Never deployed:
 * deploy.yml builds a fresh dist and adds the real ingested dataset.
 */
import { gzipSync } from "node:zlib";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const payload = JSON.parse(readFileSync("public/data/dev-fixtures.json", "utf8"));
mkdirSync("dist/data/index", { recursive: true });
writeFileSync("dist/data/index/search-docs.json.gz", gzipSync(JSON.stringify(payload.docs ?? [])));
console.log(`e2e dataset: ${payload.docs?.length ?? 0} synthetic fixture tenders`);
