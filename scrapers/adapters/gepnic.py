"""Generic NIC GePNIC adapter (spec #77).

One parser + per-deployment configuration covers ~40 verified portals
(MahaTenders, CPPP ePublishing/eProcurement, state eProcurement systems,
PSU portals). See docs/source-research.md for the verified portal matrix.

Technical model (verified across deployments):
- Apache Tapestry-style URLs: {base}{app_path}?page=<Page>&service=page
- Actionable links are session-bound ($DirectLink ... sp= tokens): we keep one
  cookie jar per run and resolve details immediately.
- Listing row grammar: Sl.No | Published | Closing | Opening |
  Title/Ref/TenderID (+detail link) | Organisation Chain.
- Tender ID is the stable key: YYYY_ORGSITE_NNNNNNN_corrseq.
- Runtime CAPTCHA guard: never proceed past a challenge - flag and stop.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from scrapers.core.adapter import AdapterMeta, FetchOutcome
from scrapers.core.amounts import parse_amount, parse_plain_number
from scrapers.core.dates import IST, parse_datetime
from scrapers.core.http import HttpClient, detect_captcha
from scrapers.core.models import (
    CanonicalTender,
    CorrigendumRef,
    ProvenanceInfo,
    TenderDocument,
    TenderIdentity,
)
from scrapers.core.registry import SourceConfig
from scrapers.core.textutil import clean_text

log = logging.getLogger("opentender.gepnic")

TENDER_ID_RE = re.compile(r"\[(\d{4}_[A-Z0-9]+_\d+_\d+)\]")
REF_RE = re.compile(r"\[([^\[\]]{3,60})\]")

PAGE_LATEST_ACTIVE = "FrontEndLatestActiveTenders"
PAGE_CLOSING_BY_DATE = "FrontEndListTendersbyDate"
PAGE_LATEST_CORRIGENDA = "FrontEndLatestActiveCorrigendums"

# Label aliases on GePNIC tender-detail pages (tolerant to version skew).
_LABEL_MAP = {
    "tender title": ("procurement.title",),
    "tender ref no": ("identity.reference_number",),
    "tender id": ("identity.source_tender_id",),
    "organisation name": ("organization.authority",),
    "organisation chain": ("organization.authority",),
    "tender category": ("procurement.category",),
    "product category": ("procurement.subcategory",),
    "tender type": ("procurement.tender_type",),
    "form of contract": ("procurement.contract_type",),
    "tender value": ("financial.estimated_value",),
    "tender value in rupees": ("financial.estimated_value",),
    "emd amount": ("financial.emd_amount",),
    "emd fee": ("financial.emd_amount",),
    "earnest money deposit": ("financial.emd_amount",),
    "tender fee": ("financial.tender_fee",),
    "document fee": ("financial.tender_fee",),
    "work item description": ("work.scope",),
    "work item title": ("procurement.title",),
    "bid submission start date": ("dates.bid_submission_start",),
    "bid submission end date": ("dates.bid_submission_end",),
    "bid opening date": ("dates.bid_opening_at",),
    "pre-bid meeting date": ("dates.pre_bid_meeting_at",),
    "pre bid meeting place": (None,),
    "publish date": ("dates.published_at",),
    "document download start date": (None,),
    "document download end date": ("dates.clarification_end",),
    "clarification start date": ("dates.clarification_start",),
    "clarification end date": ("dates.clarification_end",),
    "period of work": ("work.period_of_work_days",),
    "contract period": ("work.period_of_work_days",),
    "bid validity days": ("work.bid_validity_days",),
    "location": ("geography.location_text",),
    "pincode": ("geography.pincode",),
}


def _set_path(tender: CanonicalTender, path: str, value: object) -> None:
    section, key = path.split(".", 1)
    target = getattr(tender, section)
    try:
        setattr(target, key, value)
    except ValueError:
        log.debug("rejected %s=%r for %s", key, value, section)


class GePNICAdapter:
    """Config-driven adapter shared by all GePNIC deployments."""

    family = "gepnic"

    def __init__(self, cfg: SourceConfig):
        self.cfg = cfg
        opts = cfg.options
        self.app_path = str(opts.get("app_path", "/nicgep/app"))
        self.harvest = list(opts.get("harvest", ["latest_active"]))
        self.max_detail_per_run = int(opts.get("max_detail_per_run", 40))
        self.max_pages = int(opts.get("max_pages", 2))
        base = cfg.base_url
        self.app_url = f"{base}{self.app_path}"
        self.meta = AdapterMeta(
            source_code=cfg.id,
            source_name=cfg.name,
            portal_family="gepnic",
            base_url=base,
            region=cfg.region,
            crawl_delay=cfg.crawl_delay,
            supports_corrigenda=True,
            policy_notes=cfg.policy_notes,
        )
        self._http = HttpClient(min_delay=self.meta.crawl_delay)

    # -- public API ----------------------------------------------------------

    def fetch_incremental(self, *, since: datetime | None = None) -> Iterator[CanonicalTender]:
        outcome = self.fetch_outcome()
        yield from outcome.tenders

    def fetch_outcome(self) -> FetchOutcome:
        """Full-run orchestration used by the CLI (needs aggregate stats)."""
        outcome = FetchOutcome()
        rows: list[dict] = []
        try:
            for strategy in self.harvest:
                if strategy == "latest_active":
                    rows += self._fetch_listing(PAGE_LATEST_ACTIVE, outcome)
                elif strategy == "closing_by_date":
                    rows += self._fetch_closing_by_date(outcome)
                elif strategy == "home_widget":
                    rows += self._fetch_home_widget(outcome)
                else:
                    outcome.notes.append(f"unknown harvest strategy {strategy}")
        except Exception as exc:  # noqa: BLE001
            outcome.errors.append(f"listing failed: {type(exc).__name__}: {exc}")
            return outcome
        # dedupe rows by tender id keeping first occurrence
        seen: set[str] = set()
        unique_rows = []
        for r in rows:
            tid = r.get("tender_id")
            if tid and tid in seen:
                continue
            seen.add(tid or f"row{len(unique_rows)}")
            unique_rows.append(r)
        hydrated = 0
        for row in unique_rows:
            tender = self._row_to_tender(row)
            if tender is None:
                outcome.errors.append(f"unparseable row: {row.get('title', '')[:80]}")
                continue
            if hydrated < self.max_detail_per_run and row.get("detail_href"):
                try:
                    enriched = self._fetch_detail(row["detail_href"], tender)
                    if enriched is not None:
                        tender = enriched
                        hydrated += 1
                except Exception as exc:  # noqa: BLE001
                    # failure isolation: the listing-level record still ships
                    outcome.notes.append(
                        f"detail failed for {tender.identity.source_tender_id}: {exc}"
                    )
            outcome.tenders.append(tender)
        return outcome

    def healthcheck(self) -> dict[str, object]:
        started = datetime.now()
        ok, error = False, None
        try:
            res = self._http.get(self.app_url)
            html = res.text
            if detect_captcha(html):
                error = "captcha on landing page"
            elif "Tapestry".lower() in html.lower() or "nicgep" in html or "GePNIC".lower() in html.lower():
                ok = True
            else:
                error = "expected GePNIC markers missing"
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

    # -- harvest strategies ---------------------------------------------------

    def _fetch_listing(self, page_name: str, outcome: FetchOutcome) -> list[dict]:
        url = f"{self.app_url}?page={page_name}&service=page"
        res = self._http.get(url)
        if res.status_code != 200:
            outcome.errors.append(f"{page_name}: HTTP {res.status_code}")
            return []
        html = res.text
        if detect_captcha(html):
            outcome.captcha_hit = True
            outcome.notes.append(f"{page_name} is CAPTCHA-gated; skipped politely")
            return []
        rows = self._parse_listing(html, outcome)
        if not rows:
            outcome.degraded = True
        return rows

    def _fetch_closing_by_date(self, outcome: FetchOutcome) -> list[dict]:
        """CAPTCHA-free window verified on CPPP ePublishing."""
        url = f"{self.app_url}?page={PAGE_CLOSING_BY_DATE}&service=page"
        res = self._http.get(url)
        if res.status_code != 200:
            outcome.errors.append(f"closing_by_date: HTTP {res.status_code}")
            return []
        html = res.text
        if detect_captcha(html):
            outcome.captcha_hit = True
            outcome.notes.append("closing-by-date is CAPTCHA-gated here")
            return []
        rows = self._parse_listing(html, outcome)
        if not rows:
            outcome.degraded = True
        return rows

    def _fetch_home_widget(self, outcome: FetchOutcome) -> list[dict]:
        """Always-open fallback: 10 latest tenders widget on the app root."""
        res = self._http.get(self.app_url)
        if res.status_code != 200:
            outcome.errors.append(f"home: HTTP {res.status_code}")
            return []
        html = res.text
        if detect_captcha(html):
            outcome.captcha_hit = True
            return []
        return self._parse_listing(html, outcome)

    # -- parsing ----------------------------------------------------------------

    def _parse_listing(self, html: str, outcome: FetchOutcome) -> list[dict]:
        tree = HTMLParser(html)
        rows: list[dict] = []
        for table in tree.css("table"):
            header_cells = [
                _cell_text(th).lower()
                for th in table.css("thead th") or table.css("tr:first-child th")
            ]
            if not header_cells or "sl.no" not in " ".join(header_cells):
                continue
            body_rows = table.css("tbody tr") or table.css("tr")[1:]
            for tr in body_rows:
                cells = tr.css("td")
                if len(cells) < 5:
                    continue
                texts = [_cell_text(c) for c in cells]
                link_node = _first_link(tr)
                row = {
                    "published_raw": texts[1],
                    "closing_raw": texts[2],
                    "opening_raw": texts[3],
                    "title_block": texts[4],
                    "org_chain": texts[-1] if len(texts) > 5 else None,
                    "detail_href": urljoin(self.app_url, link_node.attributes.get("href", ""))
                    if link_node
                    else None,
                }
                m_tid = TENDER_ID_RE.search(row["title_block"])
                if m_tid:
                    row["tender_id"] = m_tid.group(1)
                refs = REF_RE.findall(row["title_block"])
                refs = [r for r in refs if not TENDER_ID_RE.fullmatch(f"[{r}]")]
                row["reference_number"] = refs[0] if refs else None
                title_text = TENDER_ID_RE.sub("", row["title_block"])
                for r in refs:
                    title_text = title_text.replace(f"[{r}]", "")
                row["title"] = clean_text(title_text.strip(" :-"))
                rows.append(row)
        return rows

    def _row_to_tender(self, row: dict) -> CanonicalTender | None:
        tender_id = row.get("tender_id")
        title = row.get("title")
        if not tender_id and not title:
            return None
        now = datetime.now(tz=IST)
        source_id = tender_id or f"hash:{hashlib.sha256(title.encode()).hexdigest()[:16]}"
        closing = parse_datetime(row.get("closing_raw"))
        status = "active" if (closing and closing > now) else "closed" if closing else "unknown"
        provenance = ProvenanceInfo(
            official_source_url=self.app_url,
            source_listing_url=row.get("source_url"),
            scraped_at=now,
            first_seen_at=now,
            last_seen_at=now,
            parser_version=f"gepnic-{self.cfg.id}-1.0.0",
            content_hash="pending",
        )
        tender = CanonicalTender(
            canonical_id=CanonicalTender.make_canonical_id(self.meta.source_code, source_id),
            identity=TenderIdentity(
                source=self.meta.source_code,
                source_portal=self.meta.base_url,
                source_tender_id=source_id,
                reference_number=clean_text(row.get("reference_number"), max_len=200),
            ),
            procurement={"title": title},
            organization={"authority": clean_text(row.get("org_chain"), max_len=500)},
            dates={
                "published_at": parse_datetime(row.get("published_raw")),
                "bid_submission_end": closing,
                "bid_opening_at": parse_datetime(row.get("opening_raw")),
            },
            status=status,
            provenance=provenance,
        )
        tender.provenance.content_hash = tender.compute_content_hash()
        return tender

    # -- detail hydration ---------------------------------------------------------

    def _fetch_detail(self, href: str, tender: CanonicalTender) -> CanonicalTender | None:
        """Resolve a session-bound $DirectLink immediately after listing fetch."""
        res = self._http.get(href)
        if res.status_code != 200:
            return None
        html = res.text
        if detect_captcha(html) or "stale session" in html.lower():
            return None
        tree = HTMLParser(html)
        applied = False
        for tr in tree.css("table tr"):
            cells = tr.css("td") or tr.css("th")
            if len(cells) < 2:
                continue
            label = _cell_text(cells[0]).strip().rstrip(":").lower()
            value = _cell_text(cells[1])
            if not label or not value:
                continue
            paths = _LABEL_MAP.get(label)
            if not paths:
                continue
            for path in paths:
                if path is None:
                    continue
                current = _get_path(tender, path)
                if current:
                    continue
                parsed_value: object
                if path.startswith(("financial.",)) :
                    parsed_value = parse_plain_number(value) or parse_amount(value)
                elif path.startswith(("dates.",)):
                    parsed_value = parse_datetime(value)
                elif path == "work.period_of_work_days":
                    num = re.search(r"\d+", value.replace(",", ""))
                    parsed_value = int(num.group()) if num else None
                elif path == "identity.source_tender_id":
                    m = TENDER_ID_RE.search(value)
                    parsed_value = m.group(1) if m else value.strip()
                elif path.startswith(("geography.",)):
                    parsed_value = clean_text(value, max_len=300)
                else:
                    parsed_value = clean_text(value)
                if parsed_value in (None, "", "NA"):
                    continue
                _set_path(tender, path, parsed_value)
                applied = True
        docs = self._parse_documents(tree)
        if docs:
            tender.documents = docs
            applied = True
        corr_links = self._parse_corrigenda_links(tree)
        if corr_links:
            tender.corrigenda = [
                CorrigendumRef(source_ref=ref, source_url=urljoin(self.app_url, href_))
                for ref, href_ in corr_links
            ]
            applied = True
        if applied:
            tender.provenance.content_hash = tender.compute_content_hash()
            return tender
        return None

    def _parse_documents(self, tree: HTMLParser) -> list[TenderDocument]:
        docs: list[TenderDocument] = []
        seen: set[str] = set()
        for node in tree.css("a[href]"):
            href = node.attributes.get("href") or ""
            if any(
                k in href.lower()
                for k in ("docdownoad", "docdownload", "downloadtenderdocs", "frontendetenderdetails")
            ) and href not in seen:
                seen.add(href)
                docs.append(
                    TenderDocument(
                        title=_cell_text(node) or "tender-document",
                        source_url=urljoin(self.app_url, href),
                        type="nit",
                    )
                )
        return docs

    def _parse_corrigenda_links(self, tree: HTMLParser) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for node in tree.css("a[href]"):
            text = _cell_text(node)
            href = node.attributes.get("href") or ""
            if text and ("corrigendum" in text.lower() or "corrigendums" in href.lower()):
                out.append((text, href))
        return out


# -- small helpers -------------------------------------------------------------


def _cell_text(node) -> str:
    return clean_text(node.text(separator=" ", deep=True), max_len=2000) or ""


def _first_link(node):
    for child in node.css("a[href]"):
        href = child.attributes.get("href") or ""
        if "$directlink" in href.lower():
            return child
    return next((c for c in node.css("a[href]")), None)


def _get_path(obj, path: str):
    section, key = path.split(".", 1)
    return getattr(getattr(obj, section), key, None)
