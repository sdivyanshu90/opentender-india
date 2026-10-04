# Source Research & Reconnaissance

**Last verified: 23 August 2026; GePNIC CAPTCHA status and coverage re-verified
4 October 2026** (see "GePNIC CAPTCHA status" below). Every claim below was
reproduced from live fetches of production portals unless explicitly marked as
assumption. Raw evidence reports live in [`docs/recon/`](recon/).

> OpenTender India is an independent open-source project and is not affiliated
> with the Government of India or any procurement authority.

---

## Status legend

| Status | Meaning |
|---|---|
| ACTIVE | Ingested by scheduled runs |
| EXPERIMENTAL | Adapter implemented; running at reduced scope while behaviour is validated |
| RESEARCHING | Portal verified real; adapter pending recon of access paths |
| DEGRADED | HTTP 200 but zero-result anomaly / parse failures detected |
| CAPTCHA_LIMITED | Core listing surfaces gated; only open widgets harvested |
| LOGIN_REQUIRED | Human authentication (OTP/DSC) required for useful data — never automated |
| POLICY_RESTRICTED | robots.txt / terms prohibit crawling; adapter ships disabled-by-default with explicit operator opt-in |
| RUNNER_BLOCKED | GitHub-hosted runner IPs blocked (documented local-run path provided) |
| TEMPORARILY_BROKEN | Was working; failing ≥2 consecutive runs (auto-flagged) |
| DEPRECATED | Portal retired or migrated |

## Source matrix

| Source | Family | Access | CAPTCHA | Documents | Corrigenda | Results | Adapter | Strategy | Status |
|---|---|---|---|---|---|---|---|---|---|
| GeM BidPlus (`bidplus.gem.gov.in`) | GeM | Public XHR JSON w/ CSRF token from `/all-bids`; cookie jar required | Login/participation + View-Contracts only | **Public PDFs**: GET `/showbidDocument/{b_id}` no auth | `/public-bid-other-details/{id}`, `/viewCorrigendum/{id}` public | `/bidresultlists` + `getBidResultView/{id}` public | `gem.py` | Daily paged delta via POST `/all-bids-data` (`payload=<JSON>&csrf_bd_gem_nk=`); Solr-shaped response; 10/page; sort Bid-End-Date-Oldest | **ACTIVE** (config) - **not ingested by hosted runs**: GeM refuses connections from GitHub-hosted runner IPs; works from Indian networks. Live API returns Solr single-value lists. Under research (4 Oct 2026) |
| CPPP ePublishing (`eprocure.gov.in/epublish/app`) | NIC GePNIC | Server-rendered HTML; Tapestry `$DirectLink` session links | **Re-verified 4 Oct 2026:** Latest Active and Closing Date listings CAPTCHA-gated; **Tenders by Organisation and each organisation's list open**; doc downloads CAPTCHA interstitial | Gated (never bypassed) | Widget + gated listing | Gated (`ResultOfTenders`) | `GePNICAdapter` (`cppp_epublish`) | `org_walk` (largest 60 orgs/day, all weekly), home widget fallback; hydrate details in-session immediately. 1,382 advertised active tenders on 4 Oct 2026 | **ACTIVE** |
| Rajasthan / Kerala / MP / Uttarakhand / J&K eProcurement | NIC GePNIC | Public HTML; login-only CAPTCHA per community scrapers (23 Aug) | **4 Oct 2026:** Latest Active gated on all five (Location and Classification also gated where checked, on Kerala); Tenders by Organisation and org lists open; runtime `captchaText` guard stops politely if challenged | Login/DSC | Listing pages | Listing pages | `GePNICAdapter` (per-site YAML) | `org_walk`, `max_orgs: 60`, 4 s delay. Advertised active tenders 4 Oct 2026: Rajasthan 4,832; Kerala 7,525; MP 5,320; Uttarakhand 725; J&K 4,767 | **EXPERIMENTAL** |
| BEL eProcurement (`eprocurebel.co.in`) | NIC GePNIC (PSU/MoD) | Public HTML | Login only (23 Aug); **4 Oct 2026:** Latest Active gated, org pages open | Login/DSC | Yes | Reduced menu | `GePNICAdapter` | `org_walk`, 5 s delay. 100 advertised active tenders on 4 Oct 2026 | **EXPERIMENTAL** |
| MahaTenders (`mahatenders.gov.in`) | NIC GePNIC | Public HTML; ⚠️ **robots.txt = `Disallow: /`** | Home widgets open; full listings/search/doc downloads CAPTCHA-gated; `sp=` detail links die with session | CAPTCHA-gated | Widget (10 latest) | Gated | `GePNICAdapter` (`mahatenders`) | Widgets + immediate in-session detail hydration only; **disabled unless `OPEN_TENDER_ALLOW_POLICY_RESTRICTED=1`** | **POLICY_RESTRICTED** |
| IREPS Works (`ireps.gov.in/eps/anonymSearch.do`) | IREPS | Anonymous form POST; zone-ID list embedded in page | No CAPTCHA on works search; ≤91-day window constraint | Via works flow anonymously | In-flow | Static `html/misc/*Awarded*.html` pages | `ireps_works.py` (WP3) | Zone-wise daily crawl inside 90-day window | **EXPERIMENTAL** (config); IREPS search is disallowed by robots.txt, so it is not part of hosted ingestion |
| IREPS Goods & Services / Supply POs | IREPS | Mobile number → image CAPTCHA → SMS OTP guest wall | **SMS OTP** (max 2/hr, IP logged) | Gated | Gated | Gated | — | Not automatable politely; human-in-the-loop only | **LOGIN_REQUIRED** |
| Karnataka KPPP (`kppp.karnataka.gov.in`) | Custom SPA | Angular-style client rendering; routes `/tender`, `/bid`, `/auction` | ? | ? | ? | ? | — | Needs JSON API reverse-engineering or headless render | **RESEARCHING** |
| Gujarat nProcure (`tender.nprocure.com`) | eProc-Suite | New host verified live; legacy host geo-fenced/timeouts | ? | ? | ? | ? | — | Recon pending on new host | **RESEARCHING** |
| Telangana / AP eProcurement | Custom Java | Auto-posting CSRF login shell at root | ? | ? | ? | ? | — | Needs JS-capable recon | **RESEARCHING** |

## GePNIC CAPTCHA status (verified 4 October 2026)

Checked live against all seven configured deployments (CPPP ePublishing,
Rajasthan, Kerala, MP, Uttarakhand, J&K, BEL).

| GePNIC page | Status |
|---|---|
| Latest Active Tenders (`FrontEndLatestActiveTenders`) | CAPTCHA-gated on all 7 |
| Tenders by Closing Date (`FrontEndListTendersbyDate`) | CAPTCHA-gated (checked on CPPP) |
| Tenders by Location / Classification | CAPTCHA-gated (checked on Kerala only) |
| **Tenders by Organisation** (`FrontEndTendersByOrganisation`) | Open: every organisation with its live tender count, linking to the organisation's full tender list, no CAPTCHA |
| App-root "Latest Tenders" widget | 10 rows, no Tender IDs; used as fallback only (not re-checked per portal on 4 Oct) |

The Tenders by Organisation page also holds a separate CAPTCHA search form;
the adapter never uses it. Largest organisation pages come back as one page
(Kerala LSGD: 5,338 rows).

Advertised active tenders on 4 Oct 2026: CPPP 1,382; Rajasthan 4,832; Kerala
7,525; MP 5,320; Uttarakhand 725; J&K 4,767; BEL 100 - 24,651 in total. The
daily cap of the 60 largest organisations per portal covers about 97% of them;
the weekly reconcile walks every organisation. These are portal-advertised
counts, not a measure of what OpenTender holds.

Before this was fixed, scheduled runs stored no tenders from 23 Aug to early
Oct 2026: first the listings became CAPTCHA-gated, then selectolax 1.0 removed
the Modest backend the parser used.

Other policy status: IREPS search is disallowed by robots.txt and stays off;
MahaTenders robots.txt disallows all crawling (`POLICY_RESTRICTED`, opt-in via
`OPEN_TENDER_ALLOW_POLICY_RESTRICTED=1` only).

## Cross-cutting GePNIC facts (verified across 9+ portals)

- Uniform Apache-Tapestry-style app at `/nicgep/app` (central: `/eprocure/app`);
  page grammar `?page=FrontEndLatestActiveTenders&service=page`.
- Actionable links are **session-bound** (`$DirectLink ... sp=S<opaque>`):
  re-requesting outside the cookie session returns "Stale Session". We keep
  one cookie jar per run and resolve details immediately after listing.
- **Stable key**: Tender ID `YYYY_ORGSITE_NNNNNNN_corrSeq` (e.g.
  `2026_WRDS_1331127_1`). Reference numbers are free text and unreliable for
  identity.
- Listing row grammar: `Sl.No | e-Published | Closing | Opening |
  Title/Ref/TenderID (+link) | Organisation Chain`. Home widgets refresh every
  15 min per portal copy.
- Runtime CAPTCHA guard: halt that deployment when `captchaText`/"Provide
  Captcha" appears. **We never solve, proxy around, or outsource challenges.**
- Version skew v1.09.22→24 observed; footer version gates parser selection.
- Churn watch: West Bengal migrating off GePNIC to `tenders.wb.gov.in`
  (notice dated 17-Aug-2026); NTPC migrated SAP SRM → GePNIC. Odisha's real
  host is `tendersodisha.gov.in`; Punjab's current host is `eproc.punjab.gov.in`.

## Ethics & safety rules enforced in code

1. Preference order: official API → feed → structured endpoint → server HTML
   → browser automation only where legitimate and necessary.
2. Descriptive User-Agent identifying the project and contact path.
3. Per-host minimum delays (3–6 s) + jitter; single concurrent request/host.
4. robots.txt consulted per host; POLICY_RESTRICTED sources stay disabled
   without an explicit operator override env var.
5. No CAPTCHA-solving services, rotating proxies, fingerprint spoofing,
   credential sharing, or private API use. Ever.

## Feasibility notes for GitHub Actions runners

- No Cloudflare/Akamai edges were observed on GeM BidPlus, CPPP, or the tested
  GePNIC instances. Indian-gov WAF precedent (data.gov.in NetScaler) blocks
  *default python-requests UA fingerprints*, not runner IPs — our descriptive
  UA avoids this class of failure.
- Geo-fencing risk exists for some state hosts (Punjab legacy, Odisha) — these
  are marked accordingly and probed by `source-health.yml` every 6 h so
  degradation is public rather than silent.

- **GeM from runners:** GeM refuses connections from GitHub-hosted runners
  (datacentre IPs) but works from Indian networks (observed 4 Oct 2026). GePNIC
  portals were reachable from runners. GeM hosted ingestion is an open item.

## Assumptions & risks (explicitly unverified)

- Long-term rate-limit tolerance of each portal (no published policies found);
  mitigated by conservative pacing + zero-result anomaly detection.
- GeM CSRF/session token rotation could change shape — parser fails loudly into
  health status rather than silently returning empty data.
- Award-data retention windows unknown on some portals.
