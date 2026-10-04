# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Ingestion revived.** Daily runs stored 0 tenders from launch until early
  Oct 2026: GePNIC listings became CAPTCHA-gated, and selectolax 1.0 removed
  the Modest backend the parser depended on. Runs now fetch again.
- **Pages deploy.** The site is served under the project sub-path
  (`BASE_PATH=/opentender-india/`) with a `404.html` SPA fallback for deep
  links; `deploy` also runs after ingestion completes (ingestion commits carry
  `[skip ci]`). Live at <https://sdivyanshu90.github.io/opentender-india/>.
- **Expired tenders** are no longer shown as active: status is derived from
  the closing time when the search dataset is built.
- Search dataset rebuilt: it is regenerated each run, tenders closed more than
  30 days ago are excluded from the browser index, and the public Tender ID is
  searchable.
- Deduplication rewritten: cross-source pairs only, candidates blocked by
  reference number and closing time instead of all-pairs comparison, groups
  formed transitively (union-find).
- CI workflows (deploy, archive, security guard, e2e) repaired.

### Added

- GePNIC `org_walk` harvest strategy: reads the open "Tenders by Organisation"
  pages, largest organisations first, `max_orgs` per portal (default 60);
  `OPEN_TENDER_MAX_ORGS` override; falls back to the home widget when empty.
  The weekly reconcile walks every organisation. All seven configured portals
  use it. Fixtures `org_list.html` / `org_tenders.html` and tests.
- `opentender build-index` quality gate: refuses an empty index or a drop of
  more than 50% (`--max-drop`) versus the previous build, exit code 4;
  `--retention-days` (30) and `--force`.
- `opentender fetch` exits 3 when nothing was fetched from any source.
- Dependabot configuration.

### Changed

- **Storage (ADR-005 amended).** The tender store and generated datasets are no
  longer committed. The store lives in the Actions cache; built datasets reach
  `deploy` as the `site-data` artifact; `status/` and monthly `archive/`
  partitions stay in git. Jobs that write shared state use the `data-commit`
  concurrency group.
- Docs: CAPTCHA status matrix re-verified 4 Oct 2026; README lists dated
  coverage (24,651 advertised active tenders across seven GePNIC portals).

### Known limitations

- GeM is not ingested by hosted runs: it refuses connections from GitHub-hosted
  runner IPs (works from Indian networks). IREPS (robots.txt) and MahaTenders
  (robots.txt, `POLICY_RESTRICTED`) are not ingested.

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
