# Governance of OpenTender India

This document describes how decisions are made, who owns what, and how data sources are admitted. It is a living document, amendable by the process it describes.

## Model: BDFL-lite evolving to maintainer council

OpenTender India currently runs a **BDFL-lite** model: the founding maintainer holds final say on contested decisions to keep the project moving, but exercises it sparingly and documents reasoning publicly.

As the contributor base grows, authority transfers incrementally to a **maintainer council**:

- **Council size:** 3–5 active maintainers, self-nominated and confirmed by existing council members.
- **Areas:** each council member owns an area — ingestion/adapters, AI pipeline, frontend, infrastructure/CI.
- **Quorum:** simple majority for routine calls; the BDFL-lite seat retains a tie-break until formally retired (target: first post-1.0 release), after which ties defer to the roadmap owner.

Any decision can be appealed by opening a Discussion tagged `governance`; the appeal is answered publicly within one week.

## Decision making

| Decision type | Process |
|---|---|
| Bug fixes, docs, test improvements | Any maintainer merges after review |
| New features | RFC issue → discussion → lazy consensus (no sustained objection in ~7 days) |
| New data source | Recon report + ethics review + council approval (see below) |
| Changes to ethics/security rules | Council supermajority (3 of 4+), never a solo call |
| Contested / deadlocked | BDFL-lite tie-break, documented in the PR or ADR |

Significant architecture choices get a short ADR under `docs/adr/` so future contributors inherit the *why*, not just the *what*.

## Source-inclusion policy

Every new data source must clear this gate before any adapter code is merged:

1. **Verified reconnaissance report** at `docs/recon/<source>-recon.md`, containing:
   - URLs verified by actual fetches (not guessed or copied from third parties),
   - robots.txt analysis,
   - presence/absence of CAPTCHA, login walls, anti-bot controls,
   - listing/detail page structure and document formats,
   - go/no-go recommendation with evidence dates.
2. **Ethics review** by at least one council member against the non-negotiables:
   - never bypass CAPTCHA/login/anti-bot controls;
   - respect robots.txt (a source disallowing all crawling ships as `POLICY_RESTRICTED`, disabled by default — see MahaTenders);
   - polite crawling with a descriptive User-Agent and sane rate limits;
   - no personal data beyond what the public record already contains.
3. **Technical review**: deterministic parser design, fixture plan, failure isolation, status wiring into health checks.

Sources may be demoted or disabled (`TEMPORARILY_BROKEN`, `POLICY_RESTRICTED`, `DEPRECATED`) unilaterally by any maintainer when health, legality, or ethics demand it; re-enabling requires the reverse review. Status changes use `status:` commits and are logged visibly on the Sources page.

## Roadmap ownership

- The public roadmap lives in `ROADMAP.md`, organized in phases.
- Each phase has an **owner** (a council member) who curates its issues, keeps scope honest, and writes phase-completion notes.
- Community proposals land as `feature_request` issues; owners triage them into the current phase, backlog, or stretch goals.
- Phase order changes require council consensus; stretch-goal promotion follows the same path.

## Data integrity commitments binding all governance

- No fabricated data anywhere (spec #98): evidence-first with citations, `NOT_FOUND` over guessing.
- `OPENROUTER_API_KEY` lives only in GitHub Actions secrets or server env — never in frontend code or bundles.
- Both standard disclaimers appear verbatim wherever users consume tender information:
  - "OpenTender India is an independent open-source project and is not affiliated with the Government of India or any procurement authority."
  - "Always verify tender information on the linked official portal before making procurement decisions or submitting a bid."

Amendments to this document follow the "new feature" path (RFC + lazy consensus) unless they alter ethics rules, which need council supermajority.
