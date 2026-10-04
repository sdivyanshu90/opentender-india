"""Notice-page adapters for Maharashtra public bodies (EXPERIMENTAL).

One config-driven family (`notice_pages`) with a `parser` option selecting the
page grammar. All pages are official, public and server-rendered; every request
goes through HttpClient (project UA, robots.txt enforced, per-host delay).

parser values:
- mahagenco   : https://www.mahagenco.in/tenders - one huge page of notices
                (`ul#tenderlst_1e`, English list); the publication timestamp is
                only present in the PDF filename (`..._YYYYMMDDHHMMSSmmm.pdf`),
                so only notices published inside `window_days` are emitted.
- mahatransco : https://www.mahatransco.in/tenders/active - HTML table, 20 rows
                per page, offset pagination (`/tenders/active/20`, `/40`, ...).
- msedcl      : https://www.mahadiscom.in/en/supplier/tenders/ - WordPress post
                grid (6 per page, `/page/N/`); only title + post date are
                listed, closing dates live inside the linked notice.

Closing dates are never invented: absent -> None and status "unknown".
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from scrapers.core.adapter import AdapterMeta, FetchOutcome
from scrapers.core.dates import IST, now_ist, parse_datetime
from scrapers.core.http import HttpClient
from scrapers.core.models import CanonicalTender, ProcurementInfo, ProvenanceInfo, TenderIdentity
from scrapers.core.registry import SourceConfig
from scrapers.core.textutil import clean_text

log = logging.getLogger("opentender.notice_pages")

PARSER_VERSION = "notice-pages-0.1.0"
STATE = "Maharashtra"

AUTHORITIES = {
    "mahagenco": "Maharashtra State Power Generation Co. Ltd (MahaGenco)",
    "mahatransco": "Maharashtra State Electricity Transmission Co. Ltd (MSETCL / MahaTransco)",
    "msedcl": "Maharashtra State Electricity Distribution Co. Ltd (MSEDCL / Mahadiscom)",
}

_PDF_TS = re.compile(r"_(\d{14})\d{0,6}\.pdf$", re.I)
_NOTICE_NO = re.compile(r"Notice\s*No\.?\s*:?\s*([A-Za-z0-9()./\-]+)", re.I)


def status_for(closing: datetime | None, now: datetime | None = None) -> str:
    if closing is None:
        return "unknown"
    return "active" if closing > (now or now_ist()) else "closed"


def build_tender(
    *,
    source: str,
    portal: str,
    source_id: str,
    title: str,
    official_url: str,
    listing_url: str | None,
    authority: str,
    published: datetime | None = None,
    start: datetime | None = None,
    closing: datetime | None = None,
    tender_number: str | None = None,
    description: str | None = None,
    department: str | None = None,
    district: str | None = None,
    parser_version: str = PARSER_VERSION,
) -> CanonicalTender:
    now = datetime.now(tz=IST)
    tender = CanonicalTender(
        canonical_id=CanonicalTender.make_canonical_id(source, source_id),
        identity=TenderIdentity(
            source=source, source_portal=portal, source_tender_id=source_id,
            tender_number=tender_number,
        ),
        procurement=ProcurementInfo(
            title=clean_text(title, max_len=500), description=clean_text(description, max_len=2000),
            procurement_type="unknown",
        ),
        organization={"authority": authority, "department": department},
        geography={"state": STATE, "district": district},
        dates={"published_at": published, "bid_submission_start": start, "bid_submission_end": closing},
        status=status_for(closing, now),
        provenance=ProvenanceInfo(
            official_source_url=official_url, source_listing_url=listing_url,
            scraped_at=now, first_seen_at=now, last_seen_at=now,
            parser_version=parser_version, content_hash="pending",
        ),
    )
    tender.provenance.content_hash = tender.compute_content_hash()
    return tender


def _text(node) -> str:
    return clean_text(node.text(separator=" ", deep=True)) or ""


def _abs_pdf(base: str, href: str) -> str:
    """Absolute URL with spaces/odd chars percent-encoded (idempotent)."""
    full = urljoin(base, href.strip())
    p = urlparse(full)
    return p._replace(path=quote(p.path, safe="/%:@+,;=()'!~-._")).geturl()


# -- page grammars (pure functions, unit-tested against fixtures) --------------

def parse_mahagenco(html: str, base_url: str = "https://www.mahagenco.in/tenders") -> list[dict]:
    tree = HTMLParser(html)
    out: list[dict] = []
    for li in tree.css("ul#tenderlst_1e > li"):
        span = li.css_first("span.item")
        link = li.css_first("a[href]")
        if span is None or link is None:
            continue
        title = _text(span)
        href = link.attributes.get("href") or ""
        if not title or ".pdf" not in href.lower():
            continue
        m = _PDF_TS.search(href)
        published = None
        if m:
            try:
                published = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=IST)
            except ValueError:
                published = None
        nm = _NOTICE_NO.search(title)
        url = _abs_pdf(base_url, href)
        out.append({
            "title": title,
            "url": url,
            "pdf_key": urlparse(url).path.rsplit("/", 1)[-1],
            "notice_no": nm.group(1).rstrip(".,") if nm else None,
            "published": published,
        })
    return out


def parse_mahatransco(html: str, base_url: str = "https://www.mahatransco.in/tenders/active") -> tuple[list[dict], str | None]:
    tree = HTMLParser(html)
    rows: list[dict] = []
    for tr in tree.css("table.CustmTable tbody tr"):
        tds = tr.css("td")
        if len(tds) < 6:
            continue
        link = tds[2].css_first("a[href]") or tds[5].css_first("a[href]")
        title = _text(tds[2])
        if not title:
            continue
        href = link.attributes.get("href") if link is not None else None
        rows.append({
            "rfx_no": _text(tds[0]),
            "zone": _text(tds[1]),
            "title": title,
            "start": parse_datetime(_text(tds[3])),
            "end": parse_datetime(_text(tds[4])),
            "url": _abs_pdf(base_url, href) if href else None,
        })
    nxt = tree.css_first("ul.pagination a[rel=next]")
    next_url = urljoin(base_url, nxt.attributes["href"]) if nxt is not None and nxt.attributes.get("href") else None
    return rows, next_url


def parse_msedcl(html: str) -> tuple[list[dict], int | None]:
    tree = HTMLParser(html)
    posts: list[dict] = []
    for wrap in tree.css("div.pp-post-wrap"):
        a = wrap.css_first("h2.pp-post-title a[href]")
        if a is None:
            continue
        cls = wrap.attributes.get("class") or ""
        pm = re.search(r"\bpost-(\d+)\b", cls)
        date_node = wrap.css_first("span.pp-post-date")
        published = None
        if date_node is not None:
            raw = _text(date_node)
            for fmt in ("%B %d, %Y, %I:%M %p", "%B %d, %Y"):
                try:
                    published = datetime.strptime(raw, fmt).replace(tzinfo=IST)
                    break
                except ValueError:
                    continue
        posts.append({
            "post_id": pm.group(1) if pm else None,
            "title": _text(a),
            "url": a.attributes["href"],
            "published": published,
        })
    nav = tree.css_first("nav.pp-posts-pagination")
    total = None
    if nav is not None and (nav.attributes.get("data-total") or "").isdigit():
        total = int(nav.attributes["data-total"])
    return posts, total


# -- adapter -------------------------------------------------------------------

class NoticePagesAdapter:
    family = "notice_pages"

    def __init__(self, cfg: SourceConfig, http: HttpClient | None = None):
        self.cfg = cfg
        opts = cfg.options
        self.parser = str(opts.get("parser", "")).lower()
        if self.parser not in AUTHORITIES:
            raise ValueError(f"notice_pages: unknown parser {self.parser!r} ({cfg.id})")
        self.window_days = int(opts.get("window_days", 60))
        self.max_pages = int(opts.get("max_pages", 3))
        self.authority = opts.get("authority") or AUTHORITIES[self.parser]
        self.meta = AdapterMeta(
            source_code=cfg.id, source_name=cfg.name, portal_family="notice_pages",
            base_url=cfg.base_url, region=cfg.region,
            crawl_delay=max(cfg.crawl_delay, 4.0),
            supports_documents=False, supports_results=False, supports_corrigenda=False,
            policy_notes="Public notice listing only; links point to the official PDFs/pages.",
        )
        self.http = http or HttpClient(min_delay=self.meta.crawl_delay)

    # -- public API ------------------------------------------------------------

    def fetch_outcome(self) -> FetchOutcome:
        outcome = FetchOutcome()
        try:
            getattr(self, f"_run_{self.parser}")(outcome)
        except Exception as exc:  # noqa: BLE001 - isolate source failures
            outcome.errors.append(f"{type(exc).__name__}: {exc}")
        return outcome

    def fetch_incremental(self, *, since: datetime | None = None):
        yield from self.fetch_outcome().tenders

    def healthcheck(self) -> dict[str, object]:
        started = datetime.now()
        ok, error = False, None
        try:
            res = self.http.get(self.cfg.base_url)
            if res.status_code != 200:
                error = f"HTTP {res.status_code}"
            elif self._has_rows(res.text):
                ok = True
            else:
                error = "expected notice rows missing"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        return {
            "source": self.meta.source_code, "ok": ok, "error": error,
            "checked_at": started.astimezone().isoformat(),
            "latency_ms": int((datetime.now() - started).total_seconds() * 1000),
        }

    def close(self) -> None:
        self.http.close()

    # -- internals -------------------------------------------------------------

    def _has_rows(self, html: str) -> bool:
        if self.parser == "mahagenco":
            return bool(parse_mahagenco(html, self.cfg.base_url))
        if self.parser == "mahatransco":
            return bool(parse_mahatransco(html, self.cfg.base_url)[0])
        return bool(parse_msedcl(html)[0])

    def _get(self, url: str, outcome: FetchOutcome) -> str | None:
        res = self.http.get(url)
        if res.status_code != 200:
            outcome.errors.append(f"HTTP {res.status_code} for {url}")
            return None
        return res.text

    def _run_mahagenco(self, outcome: FetchOutcome) -> None:
        url = self.cfg.base_url
        html = self._get(url, outcome)
        if html is None:
            return
        rows = parse_mahagenco(html, url)
        if not rows:
            outcome.degraded = True
            outcome.notes.append("no notices parsed from ul#tenderlst_1e; layout may have changed")
            return
        cutoff = now_ist() - timedelta(days=self.window_days)
        undated = 0
        for row in rows:
            if row["published"] is None:
                undated += 1
                continue
            if row["published"] < cutoff:
                continue
            outcome.tenders.append(build_tender(
                source=self.meta.source_code, portal=self.meta.base_url,
                source_id=row["pdf_key"], title=row["title"], official_url=row["url"],
                listing_url=url, authority=self.authority, published=row["published"],
                tender_number=row["notice_no"],
            ))
        outcome.notes.append(
            f"{len(rows)} notices on page; {len(outcome.tenders)} within {self.window_days}d; "
            f"{undated} without filename timestamp skipped"
        )

    def _run_mahatransco(self, outcome: FetchOutcome) -> None:
        url: str | None = self.cfg.base_url
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            if not url or url in seen:
                break
            seen.add(url)
            html = self._get(url, outcome)
            if html is None:
                return
            rows, nxt = parse_mahatransco(html, self.cfg.base_url)
            if not rows:
                if page == 1:
                    outcome.degraded = True
                    outcome.notes.append("no table rows parsed on first page; layout may have changed")
                break
            for r in rows:
                official = r["url"] or url
                sid = f"{r['rfx_no']}-{urlparse(official).path.rsplit('/', 1)[-1]}".removesuffix(".pdf")
                outcome.tenders.append(build_tender(
                    source=self.meta.source_code, portal=self.meta.base_url, source_id=sid,
                    title=r["title"], official_url=official, listing_url=url,
                    authority=self.authority, start=r["start"], closing=r["end"],
                    tender_number=r["rfx_no"] or None, department=r["zone"] or None,
                ))
            url = nxt

    def _run_msedcl(self, outcome: FetchOutcome) -> None:
        base = self.cfg.base_url.rstrip("/") + "/"
        cutoff = now_ist() - timedelta(days=self.window_days)
        for page in range(1, self.max_pages + 1):
            url = base if page == 1 else f"{base}page/{page}/"
            html = self._get(url, outcome)
            if html is None:
                return
            posts, total = parse_msedcl(html)
            if not posts:
                if page == 1:
                    outcome.degraded = True
                    outcome.notes.append("no posts parsed on first page; layout may have changed")
                break
            all_old = True
            for p in posts:
                if p["published"] is not None and p["published"] < cutoff:
                    continue
                all_old = False
                sid = f"post-{p['post_id']}" if p["post_id"] else p["url"]
                outcome.tenders.append(build_tender(
                    source=self.meta.source_code, portal=self.meta.base_url, source_id=sid,
                    title=p["title"], official_url=p["url"], listing_url=url,
                    authority=self.authority, published=p["published"],
                ))
            if all_old or (total is not None and page >= total):
                break
