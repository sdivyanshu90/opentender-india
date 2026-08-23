# Roadmap

OpenTender India is developed in phases. Owners are listed in `GOVERNANCE.md`; scope changes follow the governance process. Stretch goals land only when they don't destabilize a phase.

Current release: **0.1.0** (2026-08-23) — ingestion framework, GePNIC/GeM adapters, CLI, AI pipeline, static React frontend, CI automation.

## Phase 7 — AI copilot polish

- Tighter evidence-first behaviour: every AI claim carries a citation link to the exact source page/document; `NOT_FOUND` contract enforced end-to-end (spec #98).
- Better natural-language query handling over tender listings (filters like state, category, closing window, value bands).
- Budget/cache/queue tuning: per-user and per-run budgets, smarter cache invalidation on re-fetch.
- Prompt-injection hardening for hostile tender documents; regression fixtures of known injection payloads.
- Copilot UX in `apps/web` (`AiPanel`): streaming answers, citation chips, explicit "verify on official portal" prompts.

## Phase 8 — Compliance matrix UI

- Structured eligibility/compliance extraction (document requirements, EMD, MSE/SCST exemptions, qualification criteria) surfaced as a per-tender checklist matrix.
- Side-by-side compliance comparison across shortlisted tenders in `Compare`.
- Exportable compliance matrices (CSV/XLSX with formula-injection guards).
- Confidence indicators distinguishing deterministic parser output from AI-enriched fields.

## Phase 9 — Source expansion

- **IREPS works adapter**: Indian Railways E-procurement System (IREPS) public works tenders — preceded by a verified reconnaissance report and ethics review per the source-inclusion policy.
- **More GePNIC states**: enable additional verified state deployments from the recon roster (e.g., Tamil Nadu, Punjab, Odisha, Jharkhand, Assam), each gated by fixture tests and health wiring.
- CPPP ePublishing coverage improvements where gaps remain against GePNIC listings.

## Phase 10 — Awards & analytics dashboards

- Ingest contract award results where portals publish them publicly.
- Historical analytics: award concentration, buyer activity, winning-bidder patterns, category trends — all computed from verifiable ingested data, no fabrication.
- Dashboards in `apps/web`: state/category/buyer breakdowns, time series, shareable filtered views.
- Archive-backed queries so analytics remain reproducible as live pages change.

## Phase 11 — Archive scale-out

- Move from ad-hoc snapshots to a versioned, content-addressed archive layout with manifest indexes.
- Incremental archiving and dedupe across runs; retention policy tooling via `opentender archive`.
- Compressed long-term storage sized for multi-year tender history.
- Replay tooling: rebuild search indexes and analytics from any historical snapshot.

## Stretch goals

Unscheduled; picked up between phases or when contributors volunteer:

- **Hindi/Marathi i18n** — full frontend localization plus bilingual labels sourced deterministically where portals provide them; AI summaries optionally localized with citations preserved.
- **PWA offline mode** — service-worker caching of the last built index, bookmarks, and compare views for field/low-connectivity use.
- **Optional self-hosted SQLite mode** — run ingestion + serving against a local SQLite database instead of the static-index pipeline, for organizations that want their own private instance.

## Ground rules that apply to every phase

Never bypass CAPTCHA/login/anti-bot controls; respect robots.txt (MahaTenders stays `POLICY_RESTRICTED`, disabled by default); polite crawling with descriptive User-Agent. No fabricated data anywhere. Tender documents are hostile input. `OPENROUTER_API_KEY` never touches frontend code or bundles.

> OpenTender India is an independent open-source project and is not affiliated with the Government of India or any procurement authority.
>
> Always verify tender information on the linked official portal before making procurement decisions or submitting a bid.
