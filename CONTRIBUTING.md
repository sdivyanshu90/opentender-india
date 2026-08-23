# Contributing to OpenTender India

Thank you for contributing to an independent, AGPL-3.0 open-source project that aggregates Indian public procurement data from official portals. Contributions of code, adapters, fixtures, documentation, and reconnaissance reports are all welcome.

> OpenTender India is an independent open-source project and is not affiliated with the Government of India or any procurement authority.

## Ground rules (non-negotiable)

1. **Never bypass CAPTCHA, logins, or anti-bot controls.** No credential use, no CAPTCHA solving, no headless-browser evasion tricks. If a portal requires login or blocks automated access, its status becomes `LOGIN_REQUIRED` or `POLICY_RESTRICTED` and it stays disabled by default.
2. **Respect robots.txt.** MahaTenders is `POLICY_RESTRICTED` and disabled by default precisely because its robots.txt disallows all crawling (`Disallow: /`). It can only be enabled locally via `OPEN_TENDER_ALLOW_POLICY_RESTRICTED=1`, which is an individual's own judgement call, never a default.
3. **Crawl politely.** Descriptive User-Agent, rate limits, off-peak schedules, no hammering government infrastructure.
4. **No fabricated data.** Every field must trace back to a fetched page or document. The AI layer is evidence-first with citations and honours a strict `NOT_FOUND` contract (spec #98). Never invent tenders, values, or dates — not in code, fixtures, docs, or examples.

## Development setup

### Python (ingestion pipeline, CLI)

Requirements: Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the runtime deps (httpx, beautifulsoup4, selectolax, pydantic, typer, …) plus dev tools (pytest, ruff, mypy) and gives you the `opentender` CLI.

CLI tour:

```bash
opentender sources        # list configured sources and their status
opentender health         # probe source reachability/status
opentender fetch          # fetch listings from enabled sources
opentender validate       # schema/field validation of ingested records
opentender dedupe         # cross-source deduplication
opentender build-index    # build the static search index consumed by apps/web
opentender digest         # AI digest/enrichment pass (requires OPENROUTER_API_KEY)
opentender stats          # dataset statistics
opentender archive        # write archival snapshots
```

### Frontend (`apps/web`)

Requirements: Node 20+.

```bash
cd apps/web
npm ci
npm run dev        # Vite dev server
```

## Running tests

Python (pytest, from repo root):

```bash
pytest                 # unit tests over tests/parsers, tests/ai, etc.
pytest tests/parsers   # subset
```

Frontend (from `apps/web`):

```bash
npm run test           # vitest run
npm run typecheck      # tsc -b --noEmit
npm run build          # tsc -b && vite build
```

A PR is ready when: `pytest` passes, `npm run typecheck` and `npm run build` succeed, and `ruff check .` is clean.

## Linting

```bash
ruff check .     # line-length 120, target py310; rules E,F,I,UP,B,S,SIM
ruff format .
```

Config lives in `pyproject.toml`. Run ruff before committing; CI runs it too.

## Code style principles

- **Deterministic parsing before AI.** Extract everything you deterministically can from HTML/PDF/XLSX first (dates, values, closing times, item tables). The AI layer only enriches, summarizes, or fills gaps *on top* of parsed evidence, always citing where each claim came from, and returns `NOT_FOUND` rather than guessing. Parsers are pure functions of their input wherever possible.
- **Failure isolation per source.** One portal being down, redesigned, or returning garbage must never break other sources' ingestion or the build. Catch, log (structlog), mark the source degraded, move on.
- **Typed models at boundaries.** Raw bytes/HTML in, pydantic models out. Validate before persisting.
- **Tender documents are hostile input.** Treat every fetched PDF/XLSX/HTML as attacker-controlled: size limits, timeouts, no code execution from file content, defensive parsing everywhere.
- **Secrets stay out of the client.** `OPENROUTER_API_KEY` lives only in GitHub Actions secrets or server environment. It must never appear in frontend code, bundles, commits, logs, or issue reports.

## Adding a new source adapter

Order matters — do these steps in sequence:

1. **Research report first.** Write a reconnaissance document under `docs/recon/<source>-recon.md`: verified URLs (fetched, not guessed), robots.txt analysis, presence of CAPTCHA/login/anti-bot controls, listing structure, document formats, and a go/no-go ethics recommendation. See `docs/recon/gepnic-recon.md` for the expected depth.
2. **Ethics review.** A maintainer reviews the report against the ground rules above. If the source requires login or disallows crawling, it ships as `LOGIN_REQUIRED`/`POLICY_RESTRICTED` and disabled by default — or not at all.
3. **YAML configuration.** Add an entry to `scrapers/configs/sources.yaml` with `id`, `name`, `base_url`, `adapter`, `status`, rate-limit and politeness settings.
4. **Adapter implementation.** Add the adapter under `scrapers/adapters/` (subclass the base adapter contract). Parsing must be deterministic and fixture-driven; keep network access out of the parsing logic itself.
5. **HTML/PDF fixtures.** Save real (or realistically redacted) response samples under `tests/fixtures/<source>/`. Fixtures are the spec — tests parse them into pydantic models and assert exact fields, including edge cases (missing closing dates, multi-item BOQs, regional encodings).
6. **Tests.** pytest coverage for listing parsing, detail parsing, validation, and dedupe behaviour. Include a "portal returns garbage" case proving failure isolation.
7. **Status wiring.** Register the source in health checks and the Sources page so users see its live status.

PRs adding adapters without a prior recon report will be sent back for one.

## Pull requests

- Keep PRs focused; one adapter/feature/fix per PR.
- Fill in the PR description: what changed, why, how you tested it (commands + output summary).
- New user-visible strings should include both standard disclaimers where relevant, verbatim:
  - "OpenTender India is an independent open-source project and is not affiliated with the Government of India or any procurement authority."
  - "Always verify tender information on the linked official portal before making procurement decisions or submitting a bid."
- Do not commit secrets, personal data, or scraped bulk datasets. Fixtures only.
- Maintainers may ask for changes — expect review on ethics and data-quality grounds, not just correctness.
- By submitting a PR you agree your contribution is licensed under AGPL-3.0-or-later.

## Commit message conventions

Use conventional-ish prefixes so history stays scannable:

| Prefix | Use for |
|---|---|
| `feat:` | new user-facing capability |
| `fix:` | bug fix |
| `data:` | parser/adapter/fixture/config changes affecting ingested data |
| `status:` | source health/status flips (e.g., marking MahaTenders POLICY_RESTRICTED) |
| `ai:` | AI pipeline changes (prompts, budget/cache/queue, NOT_FOUND contract) |
| `web:` | frontend changes |
| `docs:` | documentation |
| `chore:` | tooling, CI, housekeeping |

Example: `data: add Kerala GePNIC siteCode + closing-date timezone handling`

## Getting help

Open a GitHub Discussion or an issue. For security-sensitive matters, follow `SECURITY.md` instead of filing a public issue.
