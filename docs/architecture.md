# Architecture

The full decision rationale lives in [adr/](adr/). This page is the map.

## Planes

| Plane | Technology | Runs where | Key modules |
|---|---|---|---|
| Ingestion | Python 3.10+ (httpx, selectolax, Pydantic, tenacity) | GitHub Actions daily / local | `scrapers/core`, `scrapers/adapters`, `cli.py` |
| Intelligence | Deterministic rules + budgeted OpenRouter AI | Actions nightly | `scrapers/core/parsers/documents.py`, `packages/ai/opentender_ai` |
| Delivery | React 18 + TS + Vite + Tailwind + MiniSearch + IndexedDB | GitHub Pages (static) | `apps/web/src` |

## Data flow

1. **Fetch** — each adapter pulls its permitted public surfaces with per-host
   politeness (`http.py`), a runtime CAPTCHA guard, and robots awareness. The
   GePNIC adapter runs the strategies listed per source in `sources.yaml`
   (`org_walk`, `home_widget`, `latest_active`, `closing_by_date`); the
   configured portals use `org_walk` (see "GePNIC harvest" below).
2. **Normalize** — portal rows become `CanonicalTender` records; dates parse
   via a deterministic Indian-format parser; amounts via ₹/lakh/crore rules;
   text is sanitised at parse time.
3. **Persist** — gzip JSON per tender under `data/hot/` + `data/state.json`
   index. `merge_preserving_history` keeps first_seen and never blanks fields.
   See "Storage" below: these files are not committed to git.
4. **Diff** — deterministic field-level change detection with severity
   classification (CRITICAL deadline changes → INFO notes).
5. **Documents** — hostile-input pipeline: magic-byte validation, size/zip-bomb
   limits, pypdf/openpyxl extraction, page-preserving chunking.
6. **AI enrichment** — persistent priority queue → budget manager → cache
   (SHA256 of normalized input + prompt/schema versions) → OpenRouter with
   model-fallback chain → Pydantic schema validation (repair → retry → fail).
7. **Publish** — `opentender build-index` writes the search dataset
   (`data/indexes/search-docs.json.gz`) and digest feed; tenders that closed
   more than 30 days ago are left out of the browser index (`--retention-days`).
   A quality gate refuses an empty index or one that shrank by more than 50%
   (exit code 4), keeping the previous dataset. `deploy.yml` ships the result
   with the frontend.

Cross-source dedupe (`opentender dedupe`) forms *possible-duplicate groups*
only; it never merges records. Pairs are considered only across different
sources, blocked by normalised reference number and by closing time (6-hour
buckets), scored on title, authority, state and closing date, and grouped
transitively with union-find. Each group is named after its smallest member
(`dup:<canonical_id>`).

## GePNIC harvest

Since 4 Oct 2026 the "Latest Active Tenders" and "Tenders by Closing Date"
pages are CAPTCHA-gated on all seven configured portals. `org_walk` reads the
open "Tenders by Organisation" page (organisations with live counts), then each
organisation's tender list, largest first, up to `max_orgs` (default 60;
override with `OPEN_TENDER_MAX_ORGS`). If a page is CAPTCHA-gated the adapter
stops that portal politely; it never submits the CAPTCHA search form. When the
walk yields nothing it falls back to the app-root `home_widget` (10 rows).
Details: [recon/gepnic-recon.md](recon/gepnic-recon.md).

## Storage

| What | Where | In git? |
|---|---|---|
| Per-tender records, `state.json` | `data/hot/`, `data/state.json`; Actions cache between runs | no |
| Search dataset, manifest | `data/indexes/`, `data/index/`; `site-data` artifact to deploy | no |
| Source health, feeds, AI queue | `status/`, `data/ai-queue.jsonl` | yes |
| Long-closed tenders | `archive/<source>_<YYYY>_<MM>.json.gz` (monthly, 180-day cutoff) | yes |

Rationale and consequences: [ADR-005](adr/ADR-005.md).

## CI topology

- `fetch-tenders` (daily): restore cache, fetch, validate, dedupe, AI, build
  index, tests, save cache, upload `site-data`, commit `status/`.
- `weekly-reconcile`: the same workflow via `workflow_call` with a full
  organisation walk (`OPEN_TENDER_MAX_ORGS=100000`).
- `deploy`: on push to `main` and on completion of either ingestion workflow;
  builds with `BASE_PATH=/opentender-india/`, adds the latest `site-data`,
  publishes to GitHub Pages (`404.html` copy of `index.html` for deep links).
- `source-health` (6-hourly) and `archive` (monthly). `fetch-tenders`,
  `source-health` and `archive` share the `data-commit` concurrency group.

## Frontend

- Local-first: dataset loads as compressed shards; MiniSearch index builds in
  the browser; all user state (bookmarks, notes, workflow status, saved
  searches, company profile, BYOK key, privacy mode) persists in IndexedDB.
- NLQ parser converts queries like *"solar EPC Maharashtra above ₹2 crore
  closing within 30 days"* into structured URL-encoded filters instantly,
  showing the interpreted filters so users keep control (#14).
- Tender Copilot answers from precomputed artifacts by default; live Q&A uses
  the user's own OpenRouter key over shipped evidence chunks.

## Failure isolation

- Per-source: one portal failing cannot fail the run (workflow + CLI design).
- Per-record: unreadable documents or malformed AI output degrade that record
  only, visibly.
- AI-off: the entire non-AI product is always available; UI shows "AI
  temporarily unavailable" rather than breaking.

## Repository tree (implemented)

```text
apps/web/                  frontend (Vite React TS)
  src/lib/                 types, data loading, search, nlq, filters, store, ai, export, match
  src/components/          ResultsList, FilterBar, CommandPalette, AiPanel, badges, views
  src/pages/               Home, Discover, ForYou, Saved, TenderDetail, Compare, SourcesPage, Settings
packages/schema/           canonical_tender.schema.json
packages/ai/
  opentender_ai/           provider, router hooks, budget, cache, queue, schemas, tasks
  prompts/                 versioned prompts (meta.yaml + system.md per task)
scrapers/core/             http, models, dates, amounts, textutil, adapter, dedupe, diff, store, health, registry
scrapers/core/parsers/     documents.py (secure extraction + chunking)
scrapers/adapters/         gepnic.py, gem.py
scrapers/configs/          sources.yaml
tests/                     fixtures/{gepnic,gem}, parsers/, ai/
docs/                      source-research.md, architecture/, adr/, recon/
status/                    sources.json, ai-budget.json, feeds/
.github/workflows/         fetch-tenders, weekly-reconcile, source-health, archive, ci, deploy
```
