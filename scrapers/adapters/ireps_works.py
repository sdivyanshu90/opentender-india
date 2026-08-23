"""IREPS Works-module adapter (EXPERIMENTAL).

Verified access model (2026-08, docs/source-research.md):
- anonymous works-tender advance search: POST /eps/anonymSearch.do;appsessionid=...
  (form fields searchOption, railwayZone, tenderStage, dateFrom/dateTo dd/mm/yyyy)
- zone list embedded in the search page HTML as <option value="401">NORTHERN RLY</option>
- results are server-rendered tables; stable keys are numeric tender numbers
- Goods & Services / Supply / PO searches sit behind a mobile+SMS OTP guest
  wall and are deliberately OUT OF SCOPE - we never automate that flow.

This adapter implements only the polite subset: parse the search page for
zones, then query each zone inside the <=91-day window for published tenders.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from selectolax.parser import HTMLParser

from scrapers.core.adapter import AdapterMeta, FetchOutcome
from scrapers.core.dates import IST, now_ist, parse_datetime
from scrapers.core.http import HttpClient, detect_captcha
from scrapers.core.models import (
    CanonicalTender,
    ProcurementInfo,
    ProvenanceInfo,
    TenderIdentity,
)
from scrapers.core.registry import SourceConfig
from scrapers.core.textutil import clean_text

log = logging.getLogger("opentender.ireps")

SEARCH_PAGE = "https://www.ireps.gov.in/eps/anonymSearch.do?searchParam=showPage&language=en"
SEARCH_POST = "https://www.ireps.gov.in/eps/anonymSearch.do"
ZONE_OPTION_RE = re.compile(r'<option[^>]+value="(\d{3})"[^>]*>([^<]*(?:RLY|RAILWAY)[^<]*)</option>', re.I)


class IrepsWorksAdapter:
    family = "ireps"

    def __init__(self, cfg: SourceConfig):
        self.cfg = cfg
        opts = cfg.options
        self.max_zones = int(opts.get("max_zones_per_run", 4))
        self.window_days = min(int(opts.get("window_days", 7)), 90)  # portal caps at 91
        base = "https://www.ireps.gov.in"
        self.meta = AdapterMeta(
            source_code=cfg.id,
            source_name=cfg.name,
            portal_family="ireps",
            base_url=base,
            region=cfg.region,
            crawl_delay=max(cfg.crawl_delay, 5.0),  # CRIS infrastructure: extra gentle
            supports_documents=False,
            supports_results=False,
            supports_corrigenda=False,
            policy_notes=(
                "Works module only; anonymous search has no CAPTCHA but is limited "
                "to a ~91-day window. Goods/Services/PO require SMS-OTP and are "
                "never automated."
            ),
        )
        self._http = HttpClient(min_delay=self.meta.crawl_delay)

    # -- public API ----------------------------------------------------------

    def fetch_outcome(self) -> FetchOutcome:
        outcome = FetchOutcome()
        try:
            res = self._http.get(SEARCH_PAGE)
        except Exception as exc:  # noqa: BLE001
            outcome.errors.append(f"search page fetch failed: {type(exc).__name__}: {exc}")
            return outcome
        if res.status_code != 200:
            outcome.errors.append(f"search page HTTP {res.status_code}")
            return outcome
        html = res.text
        if detect_captcha(html):
            outcome.captcha_hit = True
            outcome.notes.append("CAPTCHA on works search page; stopping politely")
            return outcome
        zones = self._parse_zones(html)
        if not zones:
            outcome.degraded = True
            outcome.notes.append("no railway-zone options found; page layout may have changed")
            return outcome
        to_date = now_ist()
        from_date = to_date - timedelta(days=self.window_days)
        for zone_id, zone_name in zones[: self.max_zones]:
            try:
                rows = self._search_zone(zone_id, zone_name, from_date, to_date, outcome)
            except Exception as exc:  # noqa: BLE001
                outcome.notes.append(f"zone {zone_name} failed independently: {exc}")
                continue
            outcome.tenders.extend(rows)
        return outcome

    def fetch_incremental(self, *, since: datetime | None = None):
        yield from self.fetch_outcome().tenders

    def healthcheck(self) -> dict[str, object]:
        started = datetime.now()
        ok, error = False, None
        try:
            res = self._http.get(SEARCH_PAGE)
            html = res.text
            if detect_captcha(html):
                error = "captcha on works search page"
            elif ZONE_OPTION_RE.search(html):
                ok = True
            else:
                error = "expected zone options missing"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        return {
            "source": self.meta.source_code,
            "ok": ok,
            "error": error,
            "checked_at": started.astimezone().isoformat(),
            "latency_ms": int((datetime.now() - started).total_seconds() * 1000),
        }

    def close(self) -> None:
        self._http.close()

    # -- internals -------------------------------------------------------------

    def _parse_zones(self, html: str) -> list[tuple[str, str]]:
        tree = HTMLParser(html)
        zones: dict[str, str] = {}
        for opt in tree.css("select option"):
            value = (opt.attributes.get("value") or "").strip()
            label = clean_text(opt.text(separator=" ", deep=True)) or ""
            if value.isdigit() and ("RLY" in label.upper() or "RAILWAY" in label.upper()):
                zones[value] = label.title()
        if not zones:  # regex fallback for non-parseable selects
            for m in ZONE_OPTION_RE.finditer(html):
                zones.setdefault(m.group(1), m.group(2).strip().title())
        return sorted(zones.items(), key=lambda kv: kv[1])

    def _search_zone(
        self,
        zone_id: str,
        zone_name: str,
        from_date: datetime,
        to_date: datetime,
        outcome: FetchOutcome,
    ) -> list[CanonicalTender]:
        form = {
            "searchOption": "2",
            "searchOptorOption": "1",
            "advancedSearch": "",
            "railwayZone": zone_id,
            "division": "",
            "bidding": "",
            "tenderStage": "1",  # Published
            "dateFrom": from_date.strftime("%d/%m/%Y"),
            "dateTo": to_date.strftime("%d/%m/%Y"),
            "dateOrderType": "C",  # closing date order
            "language": "en",
        }
        res = self._http.post(SEARCH_POST, data=form)
        if res.status_code != 200:
            raise RuntimeError(f"HTTP {res.status_code}")
        html = res.text
        if detect_captcha(html) or "Authenticate Yourself" in html:
            outcome.notes.append(f"{zone_name}: guest gate encountered; skipping")
            return []
        return [self._row_to_tender(row, zone_name) for row in self._parse_results(html)]

    def _parse_results(self, html: str) -> list[dict]:
        """Parse result table rows defensively (Struts-era markup varies)."""
        tree = HTMLParser(html)
        rows: list[dict] = []
        for tr in tree.css("table tr"):
            cells = tr.css("td")
            if len(cells) < 4:
                continue
            texts = [(clean_text(c.text(separator=" ", deep=True)) or "") for c in cells]
            # Heuristic row grammar: sl.no | tender no | description | closing | stage...
            if not texts[0].isdigit():
                continue
            rows.append({
                "sl_no": texts[0],
                "tender_no": next((t for t in texts[1:3] if re.fullmatch(r"\d{6,12}", t)), None),
                "title_block": " | ".join(t for t in texts[1:4] if t),
                "dates_raw": [t for t in texts if re.search(r"\d{2}/\d{2}/\d{4}", t)],
            })
        return rows

    def _row_to_tender(self, row: dict, zone_name: str) -> CanonicalTender | None:
        title = clean_text(row.get("title_block"), max_len=400)
        if not title:
            return None
        now = datetime.now(tz=IST)
        source_id = row.get("tender_no") or f"ireps:{zone_name}:{row['sl_no']}"
        closing_raw = next(
            (re.sub(r"[^0-9/: ]", "", d).strip() for d in reversed(row.get("dates_raw") or [])),
            None,
        )
        closing = parse_datetime(closing_raw.replace("/", "-")) if closing_raw else None
        provenance = ProvenanceInfo(
            official_source_url=SEARCH_PAGE,
            scraped_at=now,
            first_seen_at=now,
            last_seen_at=now,
            parser_version=f"ireps-{self.cfg.id}-0.1.0",
            content_hash="pending",
        )
        tender = CanonicalTender(
            canonical_id=CanonicalTender.make_canonical_id(self.meta.source_code, source_id),
            identity=TenderIdentity(
                source=self.meta.source_code,
                source_portal=self.meta.base_url,
                source_tender_id=source_id,
                tender_number=row.get("tender_no"),
            ),
            procurement=ProcurementInfo(title=title, procurement_type="works"),
            organization={"authority": f"Indian Railways — {zone_name}"},
            geography={"state": None},
            dates={"bid_submission_end": closing},
            status="active" if (closing and closing > now) else "closed" if closing else "unknown",
            provenance=provenance,
        )
        tender.provenance.content_hash = tender.compute_content_hash()
        return tender
