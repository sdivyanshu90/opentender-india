# Source Research & Reconnaissance

**Last verified: 23 August 2026.** Every claim below was reproduced from live
fetches of production portals during this session unless explicitly marked as
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
| GeM BidPlus (`bidplus.gem.gov.in`) | GeM | Public XHR JSON w/ CSRF token from `/all-bids`; cookie jar required | Login/participation + View-Contracts only | **Public PDFs**: GET `/showbidDocument/{b_id}` no auth | `/public-bid-other-details/{id}`, `/viewCorrigendum/{id}` public | `/bidresultlists` + `getBidResultView/{id}` public | `gem.py` | Daily paged delta via POST `/all-bids-data` (`payload=<JSON>&csrf_bd_gem_nk=`); Solr-shaped response; 10/page; sort Bid-End-Date-Oldest | **ACTIVE** |
| CPPP ePublishing (`eprocure.gov.in/epublish/app`) | NIC GePNIC | Server-rendered HTML; Tapestry `$DirectLink` session links | **Closing-date lists OPEN**; active/search/corrigendum/award listings CAPTCHA-gated; doc downloads CAPTCHA interstitial | Gated (never bypassed) | Widget + gated listing | Gated (`ResultOfTenders`) | `GePNICAdapter` (`cppp_epublish`) | Harvest `closing_by_date` (+14-day windows) + home widget; hydrate details in-session immediately | **ACTIVE** |
| Rajasthan / Kerala / MP / Uttarakhand / J&K eProcurement | NIC GePNIC | Public HTML; login-only CAPTCHA per community scrapers + runtime guard | Listings believed open; runtime `captchaText` guard stops politely if challenged | Login/DSC | Listing pages | Listing pages | `GePNICAdapter` (per-site YAML) | `latest_active` walk, ≤2 pages/day, 4 s delay | **EXPERIMENTAL** |
| BEL eProcurement (`eprocurebel.co.in`) | NIC GePNIC (PSU/MoD) | Public HTML | Login only | Login/DSC | Yes | Reduced menu | `GePNICAdapter` | `latest_active` walk | **EXPERIMENTAL** |
| MahaTenders (`mahatenders.gov.in`) | NIC GePNIC | Public HTML; ⚠️ **robots.txt = `Disallow: /`** | Home widgets open; full listings/search/doc downloads CAPTCHA-gated; `sp=` detail links die with session | CAPTCHA-gated | Widget (10 latest) | Gated | `GePNICAdapter` (`mahatenders`) | Widgets + immediate in-session detail hydration only; **disabled unless `OPEN_TENDER_ALLOW_POLICY_RESTRICTED=1`** | **POLICY_RESTRICTED** |
| IREPS Works (`ireps.gov.in/eps/anonymSearch.do`) | IREPS | Anonymous form POST; zone-ID list embedded in page | No CAPTCHA on works search; ≤91-day window constraint | Via works flow anonymously | In-flow | Static `html/misc/*Awarded*.html` pages | `ireps_works.py` (WP3) | Zone-wise daily crawl inside 90-day window | **EXPERIMENTAL** |
| IREPS Goods & Services / Supply POs | IREPS | Mobile number → image CAPTCHA → SMS OTP guest wall | **SMS OTP** (max 2/hr, IP logged) | Gated | Gated | Gated | — | Not automatable politely; human-in-the-loop only | **LOGIN_REQUIRED** |
| Karnataka KPPP (`kppp.karnataka.gov.in`) | Custom SPA | Angular-style client rendering; routes `/tender`, `/bid`, `/auction` | ? | ? | ? | ? | — | Needs JSON API reverse-engineering or headless render | **RESEARCHING** |
| Gujarat nProcure (`tender.nprocure.com`) | eProc-Suite | New host verified live; legacy host geo-fenced/timeouts | ? | ? | ? | ? | — | Recon pending on new host | **RESEARCHING** |
| Telangana / AP eProcurement | Custom Java | Auto-posting CSRF login shell at root | ? | ? | ? | ? | — | Needs JS-capable recon | **RESEARCHING** |

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

## Assumptions & risks (explicitly unverified)

- Long-term rate-limit tolerance of each portal (no published policies found);
  mitigated by conservative pacing + zero-result anomaly detection.
- GeM CSRF/session token rotation could change shape — parser fails loudly into
  health status rather than silently returning empty data.
- Award-data retention windows unknown on some portals.
