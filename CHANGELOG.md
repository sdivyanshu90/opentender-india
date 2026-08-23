# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-23

Initial release of OpenTender India — an independent, AGPL-3.0 open-source tender intelligence platform aggregating Indian public procurement data from official portals (GeM, CPPP ePublishing, NIC GePNIC state portals) with an AI enrichment layer via OpenRouter.

### Added

- **Ingestion framework**: source registry (`scrapers/configs/sources.yaml`) with per-source status lifecycle (`RUNNER_BLOCKED` / `LOGIN_REQUIRED` / `POLICY_RESTRICTED` / `TEMPORARILY_BROKEN` / `DEPRECATED`), health probing, polite crawling with descriptive User-Agent, robots.txt compliance, and per-source failure isolation.
- **GePNIC generic adapter**: one configurable adapter covering NIC GePNIC state/PSU deployments via `siteCode`, backed by a verified reconnaissance report (`docs/recon/gepnic-recon.md`).
- **GeM adapter** for Government e-Marketplace public tender listings.
- **CLI (`opentender`)**: `sources`, `health`, `fetch`, `validate`, `dedupe`, `build-index`, `digest`, `stats`, and `archive` commands with structlog output.
- **AI pipeline** (via OpenRouter): evidence-first summarization with citations, strict `NOT_FOUND` contract (spec #98 — no fabricated data), budget controls, response caching, and a work queue; API key confined to GitHub Actions secrets or server env, never frontend code or bundles.
- **Static React frontend** (`apps/web`, React + Vite + Tailwind): local MiniSearch-powered search over the prebuilt index, bookmarks (IndexedDB), tender comparison view, calendar export (.ics), privacy modes (local/public/personal), sources status page, and verbatim non-affiliation and verify-on-official-portal disclaimers.
- **GitHub Actions automation**: scheduled fetch, source-health monitoring, CI (pytest + ruff + vitest + typecheck/build), static deploy, weekly reconciliation, and archive snapshot workflows.
- **Test suite**: pytest unit tests with real HTML/PDF fixtures under `tests/fixtures/`, plus vitest coverage for frontend logic.
- **Governance docs**: CONTRIBUTING, Code of Conduct, Security policy, Governance model, Roadmap.

[0.1.0]: https://github.com/somu/opentender-india/releases/tag/v0.1.0
