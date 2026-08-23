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
   politeness (`http.py`), a runtime CAPTCHA guard, and robots awareness.
2. **Normalize** — portal rows become `CanonicalTender` records; dates parse
   via a deterministic Indian-format parser; amounts via ₹/lakh/crore rules;
   text is sanitised at parse time.
3. **Persist** — gzip JSON per tender under `data/hot/` + `data/state.json`
   index. `merge_preserving_history` keeps first_seen and never blanks fields.
4. **Diff** — deterministic field-level change detection with severity
   classification (CRITICAL deadline changes → INFO notes).
5. **Documents** — hostile-input pipeline: magic-byte validation, size/zip-bomb
   limits, pypdf/openpyxl extraction, page-preserving chunking.
6. **AI enrichment** — persistent priority queue → budget manager → cache
   (SHA256 of normalized input + prompt/schema versions) → OpenRouter with
   model-fallback chain → Pydantic schema validation (repair → retry → fail).
7. **Publish** — frontend shards + digest feed + `status/sources.json`.

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
