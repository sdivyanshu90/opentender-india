# Adding a source

Read the ground rules in [CONTRIBUTING.md](../CONTRIBUTING.md) first: no CAPTCHA
or login bypass, robots.txt respected, polite crawling. A new source needs a
recon report ([recon/gepnic-recon.md](recon/gepnic-recon.md) shows the
expected depth) and a maintainer ethics review before any adapter work.

## Adding a GePNIC portal

Most NIC state and PSU portals run GePNIC, so no new code is usually needed:
add an entry to `scrapers/configs/sources.yaml`.

```yaml
  - id: gepnic_example
    family: gepnic
    name: Example State eProcurement (GePNIC)
    base_url: https://example-tenders.gov.in
    app_path: /nicgep/app          # /app under /epublish for CPPP; default /nicgep/app
    region: Example State
    status: EXPERIMENTAL           # statuses: docs/source-research.md
    enabled: true
    crawl_delay: 4.0               # seconds between requests to this host
    harvest: [org_walk]
    max_orgs: 60
    max_detail_per_run: 20
    state: Example State
```

| Key | Meaning |
|---|---|
| `family: gepnic` | selects `GePNICAdapter` |
| `app_path` | Tapestry app path under `base_url` |
| `harvest` | ordered strategies: `org_walk`, `home_widget`, `latest_active`, `closing_by_date` (default `[latest_active]`) |
| `max_orgs` | `org_walk` only: visit this many organisations, largest first (default 60). The env var `OPEN_TENDER_MAX_ORGS` overrides it |
| `max_detail_per_run` | detail pages hydrated per run (default 40); the rest keep listing-level fields |
| `max_pages` | pages walked by `latest_active` (default 2) |
| `state` | single-state portals: sets the State/UT on every tender |
| `policy_notes` | free text shown for restricted sources |

Choosing a harvest strategy: check by hand which pages are open. As of
4 Oct 2026 every configured portal gates Latest Active and Closing Date behind
a CAPTCHA, while Tenders by Organisation is open, so `org_walk` is the default.
A gated page makes the adapter stop that portal (CAPTCHA guard); it never solves
or works around the challenge. If a portal's robots.txt disallows crawling, set
`status: POLICY_RESTRICTED`; the registry then keeps it disabled unless an
operator sets `OPEN_TENDER_ALLOW_POLICY_RESTRICTED=1`.

### Fixtures and tests

1. Save real, unmodified-in-structure HTML under `tests/fixtures/gepnic/`:
   the organisation list (`org_list.html`), one organisation's tender list
   (`org_tenders.html`), and a detail page. Redact personal data only. Do not
   invent rows.
2. Add or extend tests in `tests/parsers/test_adapters.py`. They build an
   adapter from a config dict (`make_adapter()`), feed it fixture HTML through
   `_parse_org_list`, `_parse_listing` and `_fetch_org_walk` (with a stubbed
   HTTP client), and assert exact fields.
3. Include a "gated page" case: the CAPTCHA guard must set `captcha_hit` and
   stop the walk without raising.
4. Run:

   ```bash
   pytest tests/parsers/test_adapters.py -q
   pytest tests/ -q
   ruff check scrapers packages cli.py tests
   ```

5. Smoke-test locally and politely, one source at a time:

   ```bash
   opentender sources
   opentender health gepnic_example
   OPEN_TENDER_MAX_ORGS=2 opentender fetch gepnic_example --limit 20
   ```

   `fetch` prints a per-source summary and notes such as
   `org_walk: visited N/M organisations, X of Y advertised tenders`; a CAPTCHA
   stop shows as `CAPTCHA encountered`.

## Other portal families

A non-GePNIC portal needs a new adapter under `scrapers/adapters/` and a
`family` branch in `scrapers/core/registry.py` (`build_adapter`). Follow the
numbered steps in CONTRIBUTING.md; parsing must stay deterministic and
fixture-driven, with network access kept out of the parsing functions.
