# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes       |
| < 0.1.0 | no        |

We patch only the latest `0.1.x` line. Upgrade before reporting against older builds.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Use GitHub's **private security advisories**: *Security* tab → *Report a vulnerability* on this repository. Include:

- affected component (parser/adapter, CLI command, AI pipeline, `apps/web`, workflow),
- reproduction steps or a malicious fixture,
- impact assessment,
- suggested fix if you have one.

You will get an acknowledgement within 5 business days. We coordinate fixes and credit reporters in release notes unless you prefer otherwise.

## Scope

### In scope

1. **API key leakage** — any path where `OPENROUTER_API_KEY` (or future secrets) could end up in frontend code/bundles, repository files, logs, workflow artifacts, or published pages. The key must only ever live in GitHub Actions secrets or server environment variables.
2. **Prompt injection via ingested content** — crafted tender titles/descriptions/documents that could manipulate AI outputs into fabricated data, exfiltrating context, or violating the evidence-first/citation contract.
3. **Document parser vulnerabilities** — hostile PDF/XLSX/HTML inputs causing crashes, unbounded memory/CPU, XML entity expansion, path traversal on archive writes, etc. Tender documents are treated as attacker-controlled input.
4. **XSS in `apps/web`** — unsanitized tender fields (titles, descriptions, document links) rendered into the DOM; unsafe markdown/HTML from AI digests.
5. **CSV/formula injection** — exported CSV/XLSX files beginning cells with `=`, `+`, `-`, `@` such that spreadsheet applications execute formulas.

### Out of scope

- **Scraping-ethics violations** (ignoring robots.txt, bypassing CAPTCHA/logins/anti-bot controls, aggressive crawling). These violate the project's conduct rules, not its security posture. Report them as conduct issues under `CODE_OF_CONDUCT.md`.
- Vulnerabilities in third-party portals themselves (report those to NIC/GeM/the respective authority).
- Missing hardening with no demonstrated exploit path, or self-XSS requiring a user to attack themselves.
- Denial of service against government portals caused by your own crawling of this project's code.

## Security-relevant design notes

- The static frontend performs local search over prebuilt indexes; it holds no secrets by design. Any finding of a secret in the bundle is critical-severity.
- AI enrichment is budget-limited, cached, queued server-side/workflow-side, and must cite sources; unverifiable claims surface as `NOT_FOUND`, never as invented facts.
- Fetchers run with timeouts, size caps, and per-source failure isolation so one hostile response cannot take down ingestion.

## Disclosure policy

We fix privately, release patched `0.1.x` versions, then publish the advisory once users have had a reasonable window to upgrade.
