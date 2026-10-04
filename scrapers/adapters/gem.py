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
import os
import re
from collections.abc import Iterator
from datetime import datetime

import httpx

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
        env_pages = os.environ.get("OPENTENDER_GEM_MAX_PAGES")
        self.max_pages = int(env_pages or opts.get("max_pages", 50))
        # newest-first so a capped daily run always picks up freshly published bids
        self.sort = str(opts.get("sort", "Bid-Start-Date-Latest"))
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
        # fail fast on datacentre-blocked networks instead of waiting out the default connect timeout
        self._http._client.timeout = httpx.Timeout(30.0, connect=8.0)

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
        total: int | None = None
        for page in range(1, self.max_pages + 1):
            docs, found, err = self._fetch_page(page, token, outcome)
            if err or not docs:
                break
            total = found if found is not None else total
            new = 0
            for doc in docs:
                tender = self._doc_to_tender(doc)
                if tender and tender.identity.source_tender_id not in seen_ids:
                    seen_ids.add(tender.identity.source_tender_id)
                    outcome.tenders.append(tender)
                    new += 1
            if new == 0:  # pagination stopped advancing
                outcome.notes.append(f"page {page}: no new bids; stopping")
                break
            if len(docs) < self.page_size or (total is not None and page * self.page_size >= total):
                break  # last page
        outcome.notes.append(
            f"gem: {len(outcome.tenders)} bids fetched (ongoing total reported: {total}, "
            f"cap {self.max_pages} pages, sort {self.sort})"
        )
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
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            outcome.errors.append(
                f"blocked from this network: cannot connect to {self.base} ({type(exc).__name__}). "
                "GeM blocks many datacentre/CI IP ranges; run from an India residential/office network."
            )
            return None
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

    def _fetch_page(self, page: int, token: str, outcome) -> tuple[list[dict], int | None, bool]:
        payload = json.dumps(
            {
                "page": page,
                "param": {"searchBid": "", "searchType": "fullText"},
                "filter": {
                    "bidStatusType": "ongoing_bids",
                    "byType": "all",
                    "highBidValue": "",
                    "byEndDate": {"from": "", "to": ""},
                    "sort": self.sort,
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
            return [], None, True
        if res.status_code != 200:
            outcome.errors.append(f"data HTTP {res.status_code} (page {page})")
            return [], None, True
        try:
            body = json.loads(res.text)
        except json.JSONDecodeError:
            outcome.degraded = True
            outcome.notes.append(f"page {page}: non-JSON response")
            return [], None, True
        if not isinstance(body, dict) or body.get("code") != 200:
            outcome.errors.append(f"API code={body.get('code') if isinstance(body, dict) else 'n/a'}")
            return [], None, True
        inner = ((body.get("response") or {}).get("response")) or {}
        found = inner.get("numFound")
        return list(inner.get("docs") or []), (int(found) if isinstance(found, (int, float)) else None), False

    def doc_url(self, doc: dict) -> str | None:
        """Public bid-document PDF (verified login-free). Mirrors the portal's own link logic."""
        b_id = doc.get("b_id")
        if not b_id:
            return None
        btype = _to_int(doc.get("b_bid_type"))
        if btype == 5:
            label = "showdirectradocumentPdf"
        elif btype == 2:
            label = "list-ra-schedules" if (_to_int(doc.get("b_eval_type")) or 0) > 0 else "showradocumentPdf"
        else:
            label = "showbidDocument"
        return f"{self.base}/{label}/{b_id}"

    def _doc_to_tender(self, doc: dict) -> CanonicalTender | None:
        doc = _unwrap_solr(doc)
        bid_number = doc.get("b_bid_number")
        b_id = doc.get("b_id")
        if not bid_number and not b_id:
            return None
        now = datetime.now(tz=IST)
        source_id = bid_number or f"bid:{b_id}"
        start = _gem_ts(doc.get("final_start_date_sort"))
        end = _gem_ts(doc.get("final_end_date_sort"))
        buyer_status = _to_int(doc.get("b_buyer_status")) or 0
        status = BUYER_STATUS.get(buyer_status, ("unknown", ""))[0]
        categories = doc.get("b_category_name") or []
        btype = _to_int(doc.get("b_bid_type"))
        is_ra = btype in (2, 5)
        doc_url = self.doc_url(doc)
        official = doc_url or f"{self.base}/bidlists"
        provenance = ProvenanceInfo(
            official_source_url=official,
            source_listing_url=self.listing_url,
            scraped_at=now,
            first_seen_at=now,
            last_seen_at=now,
            parser_version="gem-1.1.0",
            content_hash="pending",
        )
        min_name = doc.get("ba_official_details_minName")
        dept_name = doc.get("ba_official_details_deptName")
        parent_no = doc.get("b_bid_number_parent")
        parent_id = doc.get("b_id_parent")
        documents = []
        if doc_url:
            documents.append(
                TenderDocument(
                    title="Reverse auction document (official PDF)" if is_ra else "Bid document (official PDF)",
                    type="nit",
                    source_url=doc_url,
                )
            )
        if is_ra and parent_id:
            documents.append(
                TenderDocument(
                    title=f"Parent bid document ({parent_no})" if parent_no else "Parent bid document",
                    type="nit",
                    source_url=f"{self.base}/showbidDocument/{parent_id}",
                )
            )
        procurement: dict = {
            # live API (Oct 2026) no longer sends bbt_title; the item/service name is the title
            "title": clean_text(
                doc.get("bbt_title") or doc.get("bd_category_name") or (categories[0] if categories else None),
                max_len=500,
            ),
            "description": _description(doc),
            "category": clean_text(categories[0], max_len=300) if categories else None,
            "tender_type": "ra" if is_ra else "open",
        }
        if is_ra:
            procurement["procurement_type"] = "auction"
        elif str(doc.get("b_cat_id") or "").startswith("services"):
            procurement["procurement_type"] = "services"
        tender = CanonicalTender(
            canonical_id=CanonicalTender.make_canonical_id(self.meta.source_code, source_id),
            identity=TenderIdentity(
                source=self.meta.source_code,
                source_portal=self.meta.base_url,
                source_tender_id=source_id,
                tender_number=clean_text(bid_number, max_len=100),
                reference_number=clean_text(parent_no, max_len=100) if is_ra and parent_no else None,
            ),
            procurement=procurement,
            organization={
                "ministry": clean_text(min_name, max_len=200),
                "department": clean_text(dept_name, max_len=200),
                "authority": clean_text(
                    " — ".join(x for x in [min_name, dept_name] if x), max_len=400
                ),
            },
            dates={
                "published_at": parse_datetime(start),
                "bid_submission_start": parse_datetime(start),
                "bid_submission_end": parse_datetime(end),
            },
            documents=documents,
            status=status,
            provenance=provenance,
        )
        tender.provenance.content_hash = tender.compute_content_hash()
        return tender


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _description(doc: dict) -> str | None:
    """Facts the public JSON states, joined into one line. Nothing is inferred."""
    parts: list[str] = []
    qty = doc.get("b_total_quantity")
    if isinstance(qty, (int, float)) and qty > 0:
        parts.append(f"Quantity: {int(qty) if float(qty).is_integer() else qty}")
    detail = doc.get("bd_category_name")
    cat = (doc.get("b_category_name") or [None])[0]
    if detail and detail != cat:
        parts.append(f"Item details: {detail}")
    if doc.get("is_high_value") is True:
        parts.append("High-value bid")
    if _to_int(doc.get("ba_is_global_tendering")) == 1:
        parts.append("Global tender enquiry")
    if _to_int(doc.get("is_rc_bid")) == 1:
        parts.append("Rate contract bid")
    if doc.get("b_bid_number_parent"):
        parts.append(f"Reverse auction on bid {doc['b_bid_number_parent']}")
    return clean_text("; ".join(parts), max_len=1000) if parts else None


# Genuinely multi-valued on GeM; everything else is a Solr single-value list.
_GEM_LIST_FIELDS = {"b_category_name", "bid_schedule", "parent_bid_schedule"}


def _unwrap_solr(doc: dict) -> dict:
    """Live all-bids-data returns Solr multivalued fields (``"b_bid_type": [1]``)."""
    out: dict = {}
    for key, value in doc.items():
        if key in _GEM_LIST_FIELDS:
            out[key] = value if isinstance(value, list) else [value]
        elif isinstance(value, list):
            out[key] = value[0] if value else None
        else:
            out[key] = value
    return out


def _gem_ts(value) -> str | None:
    """GeM date fields arrive as epoch-millis or ISO strings depending on API version.

    The portal's own JS renders the ISO value with getUTC*() fields, i.e. the "Z"
    is cosmetic and the wall-clock digits are IST. We therefore drop the suffix
    so downstream parsing treats the digits as IST.
    """
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10**11 else value
        return datetime.fromtimestamp(seconds, tz=IST).isoformat()
    text = str(value)
    return text[:-1] if text.endswith("Z") else text
