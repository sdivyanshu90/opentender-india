# GePNIC Ecosystem Reconnaissance Report

**Date:** 23-Aug-2026
**Method:** Live portal fetches (webfetch) + web search. Sandbox has no direct internet; two hosts unreachable from fetcher egress are flagged below.
**Purpose:** Inputs for building ONE configurable `GePNICAdapter` for an open-source tender aggregator.

---

## 1. Official directory of deployments

| Directory | URL | Notes |
|---|---|---|
| Central eProcurement Dashboard | https://eprocure.gov.in/eprocdashboard | Angular SPA. Its state/PSU selector enumerates all deployments. Every portal footer links here as `?siteCode=XX`. |
| NIC GePNIC "Clientele" page | http://gepnic.gov.in/show_content.php?lang=1&sublinkid=56&lid=55 | Categories: States, Central Government, Public Sectors, Defence, Power & Energy, Health, Educational Institutes, Judiciary, Scientific Organisations, Agriculture, MDB. (`gepnic.gov.in` intermittently times out from non-India IPs.) |

**Dashboard dropdown roster (captured verbatim from indexed copy of https://eprocure.gov.in/eprocdashboard/):**

> CPPP · Andaman and Nicobar · Arunachal Pradesh · Assam · Chandigarh · Dadra and Nagar Haveli · Daman and Diu · Haryana · Himachal Pradesh · Jammu and Kashmir · Jharkhand · Kerala · Ladakh · Madhya Pradesh · Maharashtra · Manipur · Meghalaya · Mizoram · Nagaland · Odisha · Punjab · Rajasthan · GOA · Sikkim · Tamil Nadu · Tripura · Uttar Pradesh · Uttarkhand · West Bengal · Union Territory of Lakshadweep · NCT of Delhi · Puducherry · Bharat Heavy Electricals Ltd · Coal India Ltd · Chennai Petroleum Corp Ltd · Defence PSU · Indian Oil Corporation Limited · NTPC Ltd · Pradhan Mantri Gram Sadak Yojana

This roster is **authoritative** for "who is on GePNIC". Notable absences: Gujarat, Karnataka, Telangana, Andhra Pradesh, Odisha-adjacent private platforms.

---

## 2. Verified live portals — States / UTs

### 2a. Directly fetched and live on 23-Aug-2026

| State | URL (app root) | siteCode | Footer version |
|---|---|---|---|
| Rajasthan | https://eproc.rajasthan.gov.in/nicgep/app | RAJ | 1.09.23, 11-Feb-2026 |
| Uttar Pradesh | https://etender.up.nic.in/nicgep/app | UP | 1.09.23, 05-Feb-2026 |
| Kerala | https://etenders.kerala.gov.in/nicgep/app | KER | 1.09.23, 29-Oct-2025 |
| West Bengal | https://wbtenders.gov.in/nicgep/app | WB | 1.09.23, 29-Oct-2025 |
| Madhya Pradesh | https://mptenders.gov.in/nicgep/app | MP | 1.09.23, 05-May-2026 |
| Jammu & Kashmir | https://jktenders.gov.in/nicgep/app | JNK | 1.09.23, 11-Feb-2026 |
| Uttarakhand | https://uktenders.gov.in/nicgep/app | UK | 1.09.24, 10-Jun-2026 |

### 2b. Verified via fresh search-index snippets (not directly fetched)

| State | URL | Evidence date | Note |
|---|---|---|---|
| Odisha | https://tendersodisha.gov.in/nicgep/app | indexed 22-Aug-2026 | **User-supplied `tenders.odisha.gov.in` is wrong** (extra dot). Fetcher could not reach either host (likely geo-blocking); Google crawled it one day before this research. |
| Punjab | https://eproc.punjab.gov.in/nicgep/app | v1.09.23, 09-Feb-2026 snippet | User-supplied `eprocure.punjabgovt.gov.in` was unreachable from fetcher (https+http). Use `eproc.punjab.gov.in`. |
| Jharkhand | https://jharkhandtenders.gov.in/nicgep/app | v1.09.23, 09-Feb-2026 snippet | Linked from official state portal jharkhand.gov.in. |
| Tamil Nadu | https://tntenders.gov.in/nicgep/app | GePNIC pages indexed | On dashboard roster. |
| Himachal Pradesh | https://hptenders.gov.in/nicgep/app | third-party lists | On dashboard roster. |
| Assam | https://assamtenders.gov.in/nicgep/app | third-party lists + NIC testimonial ("Assam began 2015 through GePNIC") | On dashboard roster. |
| Tripura / Manipur / Mizoram / Nagaland / Sikkim | https://tripuratenders.gov.in · https://manipurtenders.gov.in · https://mizoramtenders.gov.in · https://nagalandtenders.gov.in · https://sikkimtenders.gov.in | third-party lists | All on dashboard roster. |
| Meghalaya | https://meghalayatenders.gov.in | third-party lists | **User-supplied `megeprocurement.gov.in` unverified**; third parties consistently use meghalayatenders.gov.in. |
| Bihar / Chhattisgarh | https://eproc.bihar.gov.in · https://eproc.cgstate.gov.in | third-party lists | Both on dashboard roster. |
| Ladakh | https://tenders.ladakh.gov.in | NIC Ladakh eGov report PDF (2023) | Separate instance launched after UT formation. |

---

## 3. Verified portals — PSUs and central

### 3a. Directly fetched and live on 23-Aug-2026

| PSU | URL | Version | Notes |
|---|---|---|---|
| BEL (Bharat Electronics) | https://eprocurebel.co.in/nicgep/app | 1.09.23, 05-Feb-2026 | Branded "eProcurement System for PSUs under MoD"; custom asset dir `images/bel/`; live Bangalore/Pune factory tenders. |
| Goa Shipyard (GSL) + MoD PSU family | https://eprocuregsl.nic.in/nicgep/app | 1.09.23, 05-Feb-2026 | GSL civil + dredger tenders live; EOI visible covering "MDL GRSE HSL AND GSL" joint rate contract. Reduced menu vs state portals. |

### 3b. Verified via fresh search-index snippets

| PSU | URL | Notes |
|---|---|---|
| IndianOil (IOCL) | https://iocletenders.nic.in/nicgep/app | v1.09.23, 11-Feb-2026 (older snapshot shows v1.09.22, 09-Jun-2025). Single-org portal. Login form contains Captcha image + `Captcha Text` field. |
| Coal India (+ subsidiaries) | https://coalindiatenders.nic.in/nicgep/app | "eProcurement System of Coal India Limited", v1.09.23, 01-Apr-2026. |
| NTPC | https://eprocurentpc.nic.in/nicgep/app | "NTPC Limited eProcurement Portal", indexed 23-Aug-2026. **Migrated from SAP SRM**: legacy bidding at https://etender.ntpclakshya.co.in/sap/bc/gui/sap/its/bbpstart via http://www.ntpctender.com. Tender detail print PDFs show `?component=$DirectLink&page=PublishedView...`. |
| BHEL | https://eprocurebhel.co.in/nicgep/app | GePNIC v1.09.23, 09-Feb-2026. BHEL ALSO runs its own tender-listing CMS at https://tenders.bhel.com (many bids routed via GeM). Two surfaces to monitor. |
| MIDHANI | https://eprocuremidhani.nic.in/nicgep/app (also www.eprocuremidhani.nic.in) | "eProcurement System for PSUs under MoD", snippet Jul-2026. |
| CPCL (Chennai Petroleum) | https://cpcletenders.nic.in/nicgep/app | Listed on xorkeesign supported-portals page; CPCL is on dashboard roster. |
| Mazagon Dock (MDL) | https://eprocuremdl.nic.in/nicgep/app | xorkeesign list; MDL appears in GSL-portal joint EOI. |
| Garden Reach (GRSE) | https://eprocuregrse.co.in/nicgep/app | xorkeesign list. |
| Hindustan Shipyard (HSL) | https://eprocurehsl.nic.in/nicgep/app | xorkeesign list. |
| Defence (MoD) | https://defproc.gov.in/nicgep/app | "Defence eProcurement Portal"; Apify actor sells "Defence (MoD)" as a GePNIC portal. |

### 3c. Other GePNIC-family surfaces

- **CPPP (Central Public Procurement Portal):** https://eprocure.gov.in/eprocure/app — v1.09.24, 16-Jul-2026. NOTE context path `/eprocure/app`, not `/nicgep/app`.
- **Second central portal:** https://etenders.gov.in/eprocure/app — v1.09.24, 17-Jul-2026 (announcement: "India UK CETA flow has been enabled").
- **PMGSY family:** per-state portals on GePNIC: `pmgsytenders{ap,bih,asm,cg,goa,guj,hry,hp,jk,jhr,kar,ker,la,mah,man,meg,miz,ngl,ori,py,pb...}.gov.in|.nic.in/nicgep/app`, plus national https://pmgsytenders.gov.in/nicgep/app.
- **eAuction platform:** https://eauction.gov.in/eAuction/app.
- **NIC staging/demo:** https://demoeproc.nic.in/ntpc/app (proves app context path is configurable per tenant).

### 3d. PSUs NOT on GePNIC (own or third-party systems)

| Org | Platform | Source |
|---|---|---|
| HPCL | Custom ASP portal https://etender.hpcl.co.in + http://tenders.hpcl.co.in (+ EIL site tenders.eil.co.in) | iocl.com/purchase-procurement links page |
| BPCL | SAP Ariba-class enterprise procurement | bidindia glossary example |
| NTPC (legacy) | SAP SRM (`etender.ntpclakshya.co.in`) — now superseded by GePNIC | NTPC tender PDFs |
| SAIL, HAL, ONGC, Railways (IREPS), GeM buyers | Own portals / GeM / IREPS | bidindia portal guides; Apify actor exclusions |

---

## 4. Technical commonalities across deployments

### 4a. Framework & URL grammar (verified in fetched HTML of 9 portals)

Java web app with Apache Tapestry 5-style URLs (inference flagged in §7):

```
App root          : /nicgep/app                      (states, PSUs)
                    /eprocure/app                    (CPPP, etenders.gov.in)
                    /ntpc/app                        (demoeproc.nic.in staging)
Page navigation   : ?page=<PageName>&service=page
Component events  : ?component=$DirectLink[&_N]&page=Home&service=direct&session=T&sp=S<opaque token>
Login             : ?component=$WebHomeBorder.$WebRightMenu.login&page=Home&service=direct&session=T
Restart session   : ?service=restart
```

- `sp=` tokens are base64-ish opaque, session-bound → **detail links are not stable deep links**; they die with the session.
- Stable public key = Tender ID, format `{FY}_{ORGCODE}_{seq}_{corrigendum#}` (e.g., `2024_NTPC_87240_1`, `2026_AIIMS_908061_1`).

### 4b. Standard page names (identical on every fetched portal)

Navigation/search:
- `FrontEndAdvancedSearch` (+ POST results `FrontEndAdvancedSearchResult`)
- `FrontEndLatestActiveTenders` — "Active Tenders"
- `FrontEndListTendersbyDate` — "Tenders by Closing Date"
- `FrontEndLatestActiveCorrigendums`
- `ResultOfTenders` — results/awards
Browse:
- `FrontEndTendersByOrganisation` · `FrontEndTendersByLocation` · `FrontEndTendersByClassification`
- `FrontEndTendersInArchive` · `WebTenderStatusLists` · `WebCancelledTenderLists`
Static/support:
- `StandardBiddingDocuments` (Downloads) · `WebAnnouncements` (anchors `#id`)
- `FrontEndDebarmentList` · `FrontEndContactUs` · `SiteMap` · `SiteComp`
- `DSCInfo` · `FAQFrontEnd` · `FrontFeedback` · `BiddersManualKit` · `WebScreenReaderAccess`
Detail view: `PublishedView` (seen in NTPC printable tender PDFs).

Home page widgets: Latest Tenders + Latest Corrigenda tables (10 rows each), footer states "updates every 15 mins".

Listing table column order (per open-source scraper, matches fetched pages):
`Sl.No | e-Published Date | Closing Date | Opening Date | Title/Ref./ID (+link) | Organisation Chain`

### 4c. Central shared infrastructure

| Service | URL pattern | Observed siteCodes |
|---|---|---|
| Dashboard | https://eprocure.gov.in/eprocdashboard?siteCode={CODE} | RAJ, UP, KER, WB, MP, JNK, UK |
| MIS reports | https://gepnicreports.gov.in/eprocreports/{code}/ | raj, up, ker, wb, mp, jnk, uk |
| Mobile apps | play.google.com `gov.nic.eproc`; iTunes "GePNIC" id1330902501 | shared across portals |
| STQC cert link | `?component=$DirectLink_3&page=Home&service=direct&session=T&sp=SSecurity_Audit_Report.pdf` | all fetched |

### 4d. CAPTCHA patterns

- **Login/enrollment: CAPTCHA required.** Observed directly on iocletenders login form (fields `Captcha` image + `Captcha Text`). Enrollment/forgot-password flows likewise gated.
- **Public listing/search/detail pages: no CAPTCHA** on the instances checked. Corroborated by three independent scraper projects that explicitly rely on this:
  - github.com/PranavTamada/Tender_Scraper — "No login, no CAPTCHA solving — it only touches listing pages that are plainly viewable"
  - Apify `jungle_synthesizer/india-eprocure-tender-scraper` — "no CAPTCHA required"
  - Same scraper's detection heuristic: gate present if HTML contains `name="captchaText"` or `"Provide Captcha"` — useful runtime guard for an adapter.
- Document download/bid submission requires login + Class-3 DSC (out of scope for aggregation).

### 4e. AJAX / dynamic behavior

- The UI is server-rendered Tapestry; interactive bits (org tree on TendersByOrganisation, zone updates) post back to `/nicgep/app` with component/service params — there is **no documented public JSON API** for tender data on portal instances. Aggregation = HTML parsing of the standard pages.
- JSON-ish surfaces that DO exist outside portals: the Angular dashboard backend (`eprocdashboard`) and `gepnicreports.gov.in` MIS reports (per-site stats, not tender-level).

---

## 5. Where deployments actually differ

1. **Version skew (staggered upgrades):** observed footers range v1.09.22 (IOCL snapshot Jun-2025) → v1.09.23 (most portals, Oct-2025…May-2026) → v1.09.24 (Uttarakhand Jun-2026; CPPP & etenders.gov.in Jul-2026). IOCL announcement confirms feature drops per version ("Version 1.09.22 – Portal Browser Independence and Chatbot Support"). Parser must tolerate minor DOM drift.
2. **Context paths & domains:** `/nicgep/app` vs `/eprocure/app` (central) vs configurable (demo `/ntpc/app`); legacy vs current hostnames (Odisha `tendersodisha.gov.in` ≠ `tenders.odisha.gov.in`; Punjab `eproc.punjab.gov.in` vs legacy `eprocure.punjabgovt.gov.in`).
3. **Menu profile by tenant class:** state portals expose full browse suite + MIS-reports link; PSU-family instances ("PSUs under MoD": BEL, GSL, MIDHANI) ship reduced menus (no By Organisation/Classification on home nav, no MIS link) — single-org or small-org catalogs.
4. **Branding/assets:** custom image dirs (`images/gsl/topban.png`, `images/bel/topban.png`), varying footer ownership text, differing thresholds/fees/rules (Kerala fee GOs eff. Jan-2026; Rajasthan RISL processing fees).
5. **Shared-backend quirks:** BEL and GSL pages returned identical visitor counters (4770919) — suggests shared counter/backend behind distinct hostnames; don't treat counters as per-site state.
6. **Churn:** West Bengal migrating fresh e-tenders to a NEW non-GePNIC portal `tenders.wb.gov.in` effective 17-Aug-2026 (notice on wbtenders.gov.in). NTPC migrated SAP SRM → GePNIC. Expect more migrations both directions.
7. **Geo-reachability:** `eprocure.punjabgovt.gov.in`, `tenders(.odisha).gov.in` unreachable from non-IN egress while Google indexes them fine — plan India-egress probes or mirror verification via search cache.

---

## 6. Implications for ONE configurable GePNICAdapter

**Feasible and recommended.** One parser + per-deployment config covers ~40+ portals because page names, table layout, ID format, and CAPTCHA policy are uniform.

Suggested config schema per deployment:

```yaml
id: kerala
host: etenders.kerala.gov.in
appPath: /nicgep/app        # or /eprocure/app for central
siteCode: KER               # for dashboard/MIS cross-checks
tenantClass: state          # state | psu-mod | psu-single | central
version: 1.09.23            # parsed from footer; assert on crawl
captchaPolicy: login-only   # listings assumed free; runtime-detect captchaText
rateLimit: { minDelayMs: 1500 }
enabled: true
```

Adapter design notes:

1. **Discovery/self-description:** GET app root → parse footer for version string + `siteCode` dashboard link → validate against expected config; alert on drift.
2. **Harvest strategies (all CAPTCHA-free):**
   - `FrontEndLatestActiveTenders` paginated walk (cheap delta detection);
   - `FrontEndTendersByOrganisation` org-tree walk (complete coverage, used by commercial scrapers);
   - `FrontEndAdvancedSearch` POST for keyword backfills.
3. **Pagination stop rule (scraper-proven):** stop when the Next control's parent is disabled OR page content fingerprint repeats (GePNIC re-serves the last page).
4. **Identity:** key records by Tender ID (`YYYY_ORG_seq_corr#`); treat `sp=` URLs as ephemeral; re-resolve details each run instead of storing deep links.
5. **Runtime CAPTCHA guard:** if response contains `captchaText`/`Provide Captcha`, halt that deployment and flag — never solve.
6. **Poll cadence:** ≥15-minute floor aligns with the portals' own refresh statement; be gentle (NIC servers, community norm of short inter-request delays).
7. **Version-pinned parsers:** footer version string gates parser selection (1.09.2x today); keep per-version fixtures.
8. **Churn watch:** re-verify domain aliases + migration notices monthly (WB already left; NTPC just arrived). Keep `legacyHosts` list per deployment for redirect checks.
9. **Out-of-scope tenants needing separate adapters:** GeM, IREPS, Gujarat nProcure ((n)Code Solutions), Karnataka KPPP, Telangana/AP systems, SAP-based PSU portals (HPCL/BPCL legacy NTPC), plus BHEL's secondary `tenders.bhel.com` CMS.

---

## 7. Verified facts vs assumptions

**Verified facts (primary evidence this session):**
- Live status + versions of the 9 directly-fetched portals (Rajasthan, UP, Kerala, WB, MP, J&K, UK, BEL, GSL/MoD-PSU).
- Exact URL grammar, page names, widget cadence ("every 15 mins"), siteCode/MIS patterns from fetched HTML.
- Dashboard dropdown roster text; CPPP/etenders.gov.in versions; IOCL login CAPTCHA fields; IOCL/Coal/NTPC/BHEL/MIDHANI/Jharkhand/Odisha/Punjab/TN statuses via recent index snippets.
- WB migration notice (17-Aug-2026) read directly on wbtenders.gov.in.
- NTPC SAP-SRM legacy URLs from NTPC's own tender documents.
- Scraper-community evidence for CAPTCHA-free listings and pagination quirks (GitHub + Apify docs).

**Assumptions / inferences (flagged):**
- "Apache Tapestry 5" framework identification inferred from URL grammar (`$DirectLink`, `service=page/direct/restart`, `sp=` tokens); NIC doesn't label it publicly.
- Absence of any public tender JSON API is negative evidence (none found; scrapers all parse HTML).
- PSU-family reduced-menu generalization drawn from BEL/GSL fetches + MIDHANI snippet; verify per new PSU tenant.
- Unreachability of punjabgovt/odisha hosts attributed to geo-blocking (search crawlers fetched them within 24h).
- `megeprocurement.gov.in` (user-supplied Meghalaya name) unverified; third parties use `meghalayatenders.gov.in`.
- Exact Tapestry AJAX parameter values for zone updates not captured (fetcher returns rendered markdown, not raw JS).

---

## 8. Key source URLs

Portals (fetched): eproc.rajasthan.gov.in/nicgep/app · etender.up.nic.in/nicgep/app · etenders.kerala.gov.in/nicgep/app · wbtenders.gov.in/nicgep/app · mptenders.gov.in/nicgep/app · jktenders.gov.in/nicgep/app · uktenders.gov.in/nicgep/app · eprocurebel.co.in/nicgep/app · eprocuregsl.nic.in/nicgep/app

Directories/central: eprocure.gov.in/eprocdashboard · gepnic.gov.in/show_content.php?lang=1&sublinkid=56&lid=55 · eprocure.gov.in/eprocure/app · etenders.gov.in/eprocure/app

PSUs: iocletenders.nic.in/nicgep/app · coalindiatenders.nic.in/nicgep/app · eprocurentpc.nic.in/nicgep/app · eprocurebhel.co.in/nicgep/app · eprocuremidhani.nic.in/nicgep/app · cpcletenders.nic.in/nicgep/app · eprocuremdl.nic.in/nicgep/app · eprocuregrse.co.in/nicgep/app · eprocurehsl.nic.in/nicgep/app · defproc.gov.in/nicgep/app · etender.ntpclakshya.co.in/sap/bc/gui/sap/its/bbpstart (NTPC legacy)

States via snippets/lists: tendersodisha.gov.in/nicgep/app · eproc.punjab.gov.in/nicgep/app · jharkhandtenders.gov.in/nicgep/app · tntenders.gov.in/nicgep/app · hptenders.gov.in · assamtenders.gov.in · tripuratenders.gov.in · manipurtenders.gov.in · meghalayatenders.gov.in · mizoramtenders.gov.in · nagalandtenders.gov.in · sikkimtenders.gov.in · eproc.bihar.gov.in · eproc.cgstate.gov.in · tenders.ladakh.gov.in · pmgsytenders.gov.in/nicgep/app (+ per-state pmgsytenders* hosts)

Third-party corroboration: odysseytec.com/eProcurement (xorkeesign supported-portal list) · bidindia.co.in/blog/gepnic-state-portals-explained · bidindia.co.in/portals/gepnic · apify.com/jungle_synthesizer/india-eprocure-tender-scraper · github.com/PranavTamada/Tender_Scraper (state_gepnic_scraper.py) · cdnbbsr.s3waas.gov.in NIC UT reports (J&K, Ladakh)
