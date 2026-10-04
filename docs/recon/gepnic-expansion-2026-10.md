# GePNIC expansion recon, 2026-10-04

Method: `scrapers.core.http.HttpClient` (project UA, robots.txt enforced, 4 s delay, sequential), one GET per portal of `<base><app_path>?page=FrontEndTendersByOrganisation&service=page`, parsed with `GePNICAdapter._parse_org_list`. No CAPTCHA contact, no login, no proxies, no TLS verification bypass. Probe script: scratchpad/expansion/probe.py. Candidate hosts come from docs/recon/gepnic-recon.md, docs/source-research.md and web search of NIC state portal lists; hosts that were guessed (Haryana, Goa, Arunachal, Chandigarh, Puducherry, Andaman, Lakshadweep, Delhi, DNH&DD) are marked in notes below.

| Portal | URL | HTTP | Result | Orgs | Advertised tenders |
|---|---|---|---|---|---|
| CPPP eProcure | https://eprocure.gov.in/eprocure/app | 200 | ADDED | 248 | 2527 |
| etenders.gov.in (CPPP alias) | https://etenders.gov.in/eprocure/app | 200 | ADDED | 83 | 2291 |
| Uttar Pradesh | https://etender.up.nic.in/nicgep/app | 200 | ADDED | 133 | 12149 |
| Haryana | https://haryanaeprocurement.gov.in/nicgep/app | - | CONNECT_TIMEOUT | 0 | 0 |
| Tamil Nadu | https://tntenders.gov.in/nicgep/app | 200 | ADDED | 68 | 5746 |
| Odisha | https://tendersodisha.gov.in/nicgep/app | 200 | ADDED | 68 | 1644 |
| Punjab | https://eproc.punjab.gov.in/nicgep/app | 200 | ADDED | 34 | 3641 |
| Himachal Pradesh | https://hptenders.gov.in/nicgep/app | 200 | ADDED | 50 | 1182 |
| Assam | https://assamtenders.gov.in/nicgep/app | 200 | ADDED | 42 | 516 |
| Tripura | https://tripuratenders.gov.in/nicgep/app | 200 | ADDED | 35 | 333 |
| Manipur | https://manipurtenders.gov.in/nicgep/app | 200 | ADDED | 15 | 36 |
| Meghalaya | https://meghalayatenders.gov.in/nicgep/app | 200 | ADDED | 6 | 20 |
| Mizoram | https://mizoramtenders.gov.in/nicgep/app | 200 | CAPTCHA_GATED org list (skipped) | 0 | 0 |
| Nagaland | https://nagalandtenders.gov.in/nicgep/app | 200 | ADDED | 4 | 5 |
| Arunachal Pradesh | https://arunachaltenders.gov.in/nicgep/app | 200 | ADDED | 5 | 10 |
| Sikkim | https://sikkimtenders.gov.in/nicgep/app | - | DNS_FAILED | 0 | 0 |
| Goa | https://goaeprocure.gov.in/nicgep/app | - | DNS_FAILED | 0 | 0 |
| Chandigarh | https://etenders.chd.nic.in/nicgep/app | 200 | ADDED | 6 | 310 |
| Puducherry | https://pudutenders.gov.in/nicgep/app | 200 | ADDED | 8 | 63 |
| Ladakh | https://tenders.ladakh.gov.in/nicgep/app | - | TLS_CERT_ERROR (not bypassed) | 0 | 0 |
| Andaman & Nicobar | https://eprocure.andaman.gov.in/nicgep/app | - | DNS_FAILED | 0 | 0 |
| Lakshadweep | https://tendersutl.gov.in/nicgep/app | 200 | ADDED | 2 | 20 |
| Delhi | https://govtprocurement.delhi.gov.in/nicgep/app | 200 | ADDED | 17 | 714 |
| Jharkhand | https://jharkhandtenders.gov.in/nicgep/app | 200 | ADDED | 41 | 672 |
| Chhattisgarh | https://eproc.cgstate.gov.in/nicgep/app | 404 | HTTP_404 (app path unconfirmed) | 0 | 0 |
| Bihar | https://eproc2.bihar.gov.in/EPSV2Web/ | - | TLS_CERT_ERROR (not bypassed) | 0 | 0 |
| West Bengal | https://wbtenders.gov.in/nicgep/app | 200 | ADDED | 96 | 2572 |
| Dadra & Nagar Haveli and Daman & Diu | https://ddtenders.gov.in/nicgep/app | 200 | ADDED | 2 | 14 |
| PMGSY national | https://pmgsytenders.gov.in/nicgep/app | 200 | ADDED | 17 | 358 |
| Defence Procurement | https://defproc.gov.in/nicgep/app | 200 | ADDED | 11 | 4618 |
| IOCL | https://iocletenders.nic.in/nicgep/app | 200 | ADDED | 1 | 224 |
| Coal India | https://coalindiatenders.nic.in/nicgep/app | 200 | ADDED | 10 | 625 |
| NTPC | https://eprocurentpc.nic.in/nicgep/app | 200 | ADDED | 5 | 448 |
| BHEL | https://eprocurebhel.co.in/nicgep/app | 200 | ADDED | 1 | 498 |
| MIDHANI | https://eprocuremidhani.nic.in/nicgep/app | 200 | DUPLICATE of gepnic_gsl (same 7 orgs/100 tenders; shared MoD PSU instance) | 7 | 100 |
| CPCL | https://cpcletenders.nic.in/nicgep/app | 200 | ADDED | 1 | 3 |
| Mazagon Dock | https://eprocuremdl.nic.in/nicgep/app | 200 | DUPLICATE of gepnic_gsl (same 7 orgs/100 tenders; shared MoD PSU instance) | 7 | 100 |
| GRSE | https://eprocuregrse.co.in/nicgep/app | 200 | DUPLICATE of gepnic_gsl (same 7 orgs/100 tenders; shared MoD PSU instance) | 7 | 100 |
| Hindustan Shipyard | https://eprocurehsl.nic.in/nicgep/app | 200 | DUPLICATE of gepnic_gsl (same 7 orgs/100 tenders; shared MoD PSU instance) | 7 | 100 |
| Goa Shipyard | https://eprocuregsl.nic.in/nicgep/app | 200 | ADDED | 7 | 100 |

**Portals probed:** 40. **Added to gepnic-expansion.yaml:** 28. **Grand total of advertised active tenders across the added portals: 41339** (live counts from the org lists; overlap between the two central CPPP hosts and PMGSY/Defence aggregators is possible and is handled by dedupe).

## Notes

- Not re-probed: MahaTenders (robots Disallow /, POLICY_RESTRICTED) and the existing sources.yaml entries (cppp_epublish, Rajasthan, Kerala, MP, Uttarakhand, J&K, BEL).
- eprocure.gov.in/eprocure/app (248 orgs) and etenders.gov.in/eprocure/app (83 orgs) return different counts, so they are listed as separate deployments.
- West Bengal wbtenders.gov.in still served an open org list (96 orgs) on this date despite the reported migration; added, but should be re-checked.
- Mazagon Dock, GRSE, HSL, MIDHANI and Goa Shipyard return an identical 7-org/100-tender list (shared MoD PSU instance); only gepnic_gsl is enabled to avoid double counting.
- Not harvestable now: Haryana (connect timeout), Sikkim, Goa (DNS), Andaman (DNS; hosts may be wrong or geo-blocked), Ladakh and Bihar (TLS cert failure from this runner), Chhattisgarh (404 at /nicgep/app, true path unconfirmed), Mizoram (org list CAPTCHA-gated). Not retried to stay within the 2-request budget; retry from another network or after confirming hosts.
- Maharashtra, Karnataka, Gujarat, Telangana, AP run non-GePNIC or restricted portals and are out of scope here.
