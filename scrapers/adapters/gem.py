"""GeM BidPlus adapter (spec #78).

Public, login-free access verified 2026-08:
- listings: POST {base}/all-bids-data with payload=<JSON>&csrf_bd_gem_nk=<token>
  (CSRF token scraped from GET /all-bids; session cookie jar required)
- response: Solr-shaped JSON {response:{response:{numFound,docs[]}}}
- bid documents are public: GET /showbidDocument/{b_id}
- results: /bidresultlists + getBidResultView pages
No CAPTCHA on these public surfaces; we never touch login/participation flows.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from datetime import datetime

from scrapers.core.adapter import AdapterMeta
from scrapers.core.dates import IST, parse_datetime
from scrapers.core.http import HttpClient, detect_captcha
from scrapers.core.models import (
    CanonicalTender,
    ProvenanceInfo,
    TenderDocument,
    TenderIdentity,
)
from scrapers.core.registry import SourceConfig
from scrapers.core.textutil import clean_text

log = logging.getLogger("opentender.gem")

CSRF_RE = re.compile(r"csrf_bd_gem_nk[\"'=\s:]+([0-9a-f]{32})", re.I)

BUYER_STATUS = {
    0: ("active", "Not Evaluated"),
    1: ("closed", "Technical Evaluation"),
    2: ("closed", "Financial Evaluation"),
    3: ("awarded", "Bid Award"),
}


class GemAdapter:
    family = "gem"

    def __init__(self, cfg: SourceConfig):
        self.cfg = cfg
        opts = cfg.options
        self.base = cfg.base_url.rstrip("/")
        self.listing_url = f"{self.base}/all-bids"
        self.data_url = f"{self.base}/all-bids-data"
        self.max_pages = int(opts.get("max_pages", 3))
        self.page_size = 10  # server-side fixed
        self.meta = AdapterMeta(
            source_code=cfg.id,
            source_name=cfg.name,
            portal_family="gem",
            base_url=self.base,
            region=cfg.region,
            crawl_delay=cfg.crawl_delay,
            supports_documents=True,
            supports_results=True,
            supports_corrigenda=True,
            policy_notes=cfg.policy_notes,
        )
        self._http = HttpClient(min_delay=cfg.crawl_delay)

    # -- public API ----------------------------------------------------------

    def fetch_incremental(self, *, since: datetime | None = None) -> Iterator[CanonicalTender]:
        outcome = self.fetch_outcome()
        yield from outcome.tenders

    def fetch_outcome(self):
        from scrapers.core.adapter import FetchOutcome

        outcome = FetchOutcome()
        token = self._get_csrf_token(outcome)
        if token is None:
            return outcome
        seen_ids: set[str] = set()
        for page in range(1, self.max_pages + 1):
            docs, err = self._fetch_page(page, token, outcome)
            if err or not docs:
                break
            for doc in docs:
                tender = self._doc_to_tender(doc)
                if tender and tender.identity.source_tender_id not in seen_ids:
                    seen_ids.add(tender.identity.source_tender_id)
                    outcome.tenders.append(tender)
            if len(seen_ids) < page * self.page_size - len(docs):  # exhausted
                break
        return outcome

    def healthcheck(self) -> dict[str, object]:
        started = datetime.now()
        ok, error = False, None
        try:
            res = self._http.get(self.listing_url)
            html = res.text
            if detect_captcha(html):
                error = "captcha encountered"
            elif CSRF_RE.search(html):
                ok = True
            else:
                error = "listing page missing expected markers"
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

    # -- internals -----------------------------------------------------------

    def _get_csrf_token(self, outcome) -> str | None:
        try:
            res = self._http.get(self.listing_url)
        except Exception as exc:  # noqa: BLE001
            outcome.errors.append(f"listing fetch failed: {type(exc).__name__}: {exc}")
            return None
        if res.status_code != 200:
            outcome.errors.append(f"listing HTTP {res.status_code}")
            return None
        html = res.text
        if detect_captcha(html):
            outcome.captcha_hit = True
            outcome.notes.append("CAPTCHA on listing page; stopping politely")
            return None
        m = CSRF_RE.search(html)
        if not m:
            outcome.degraded = True
            outcome.notes.append("CSRF token not found; portal layout may have changed")
            return None
        return m.group(1)

    def _fetch_page(self, page: int, token: str, outcome) -> tuple[list[dict], bool]:
        payload = json.dumps(
            {
                "page": page,
                "param": {"searchBid": "", "searchType": "fullText"},
                "filter": {
                    "bidStatusType": "ongoing_bids",
                    "byType": "all",
                    "highBidValue": "",
                    "byEndDate": {"from": "", "to": ""},
                    "sort": "Bid-End-Date-Oldest",
                },
            }
        )
        try:
            res = self._http.post(
                self.data_url,
                data={"payload": payload, "csrf_bd_gem_nk": token},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
        except Exception as exc:  # noqa: BLE001
            outcome.errors.append(f"data fetch failed: {type(exc).__name__}: {exc}")
            return [], True
        if res.status_code != 200:
            outcome.errors.append(f"data HTTP {res.status_code} (page {page})")
            return [], True
        try:
            body = json.loads(res.text)
        except json.JSONDecodeError:
            outcome.degraded = True
            outcome.notes.append(f"page {page}: non-JSON response")
            return [], True
        if isinstance(body, dict) and body.get("code") != 200:
            outcome.errors.append(f"API code={body.get('code')}")
            return [], True
        inner = ((body.get("response") or {}).get("response")) or {}
        return list(inner.get("docs") or []), False

    def _doc_to_tender(self, doc: dict) -> CanonicalTender | None:
        bid_number = doc.get("b_bid_number")
        b_id = doc.get("b_id")
        if not bid_number and not b_id:
            return None
        now = datetime.now(tz=IST)
        source_id = bid_number or f"bid:{b_id}"
        start_raw = _gem_ts(doc.get("final_start_date_sort"))
        end_raw = _gem_ts(doc.get("final_end_date_sort"))
        status = "active" if doc.get("b_buyer_status", 0) == 0 else BUYER_STATUS.get(int(doc.get("b_buyer_status", 0)), ("unknown", ""))[0]
        categories = doc.get("b_category_name") or []
        official = f"{self.base}/bidlists"  # stable public surface for this record class
        detail_hint = (
            f"https://bidplus.gem.gov.in/showbidDocument/{b_id}" if b_id else None
        )
        provenance = ProvenanceInfo(
            official_source_url=official,
            scraped_at=now,
            first_seen_at=now,
            last_seen_at=now,
            parser_version=f"gem-1.0.0",
            content_hash="pending",
        )
        min_name = doc.get("ba_official_details_minName")
        dept_name = doc.get("ba_official_details_deptName")
        tender = CanonicalTender(
            canonical_id=CanonicalTender.make_canonical_id(self.meta.source_code, source_id),
            identity=TenderIdentity(
                source=self.meta.source_code,
                source_portal=self.meta.base_url,
                source_tender_id=source_id,
                tender_number=clean_text(bid_number, max_len=100),
            ),
            procurement={
                "title": clean_text(doc.get("bbt_title"), max_len=500),
                "category": clean_text(categories[0], max_len=300) if categories else None,
                "tender_type": "ra" if int(doc.get("b_bid_type", 1) or 1) == 2 else "open",
            },
            organization={
                "ministry": clean_text(min_name, max_len=200),
                "department": clean_text(dept_name, max_len=200),
                "authority": clean_text(
                    " — ".join(x for x in [min_name, dept_name] if x), max_len=400
                ),
            },
            dates={
                "published_at": parse_datetime(start_raw) if isinstance(start_raw, str) else None,
                "bid_submission_start": parse_datetime(start_raw) if isinstance(start_raw, str) else None,
                "bid_submission_end": parse_datetime(end_raw) if isinstance(end_raw, str) else None,
            },
            documents=(
                [
                    TenderDocument(
                        title="Bid document (official PDF)",
                        type="nit",
                        source_url=detail_hint,
                    )
                ]
                if detail_hint
                else []
            ),
            status=status,
            provenance=provenance,
        )
        tender.provenance.content_hash = tender.compute_content_hash()
        return tender


def _gem_ts(value) -> str | None:
    """GeM date fields arrive as epoch-millis or ISO strings depending on API version."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10**11 else value
        return datetime.fromtimestamp(seconds, tz=IST).isoformat()
    return str(value)
