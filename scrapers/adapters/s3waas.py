"""NIC S3WaaS district-site tender adapter (EXPERIMENTAL).

S3WaaS is the WordPress template shared by most Indian district sites. Tenders
live at <base>/en/notice_category/tenders/ (active, often empty) and
<base>/en/past-notices/tenders/ (archive, newest first, /page/N pagination).
Table grammar: Title | Description | Start Date | End Date | File (PDF on
cdn.s3waas.gov.in). Tenders are keyed by a hash of the PDF URL.

Paging stops at `max_pages`, on an empty page, when no next page link exists,
or when a whole page is older than `window_days` (and already closed).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from scrapers.adapters.notice_pages import _abs_pdf, _text, build_tender
from scrapers.core.adapter import AdapterMeta, FetchOutcome
from scrapers.core.dates import now_ist, parse_datetime
from scrapers.core.http import HttpClient
from scrapers.core.registry import SourceConfig

log = logging.getLogger("opentender.s3waas")

LISTINGS = ("/en/notice_category/tenders/", "/en/past-notices/tenders/")
PARSER_VERSION = "s3waas-0.1.0"


def is_s3waas(html: str) -> bool:
    low = html.lower()
    return "s3waas" in low or 'class="pegination"' in low


def parse_listing(html: str, page_url: str) -> tuple[list[dict], bool]:
    """Return (rows, has_next_page)."""
    tree = HTMLParser(html)
    rows: list[dict] = []
    for tr in tree.css("table tbody tr"):
        tds = tr.css("td")
        if len(tds) < 4:
            continue
        title = _text(tds[0])
        if not title:
            continue
        for junk in tds[1].css("pre"):  # leaked translate-widget markup
            junk.decompose()
        desc = _text(tds[1]) or None
        if desc == title:
            desc = None
        link = tr.css_first("a.pdf-download-link[href]") or tr.css_first("a[href$='.pdf']")
        href = link.attributes.get("href") if link is not None else None
        rows.append({
            "title": title,
            "description": desc,
            "start": parse_datetime(_text(tds[2])),
            "end": parse_datetime(_text(tds[3])),
            "pdf_url": _abs_pdf(page_url, href) if href else None,
        })
    has_next = _has_later_page(tree)
    return rows, has_next


def _has_later_page(tree) -> bool:
    cur_no = None
    cur = tree.css_first("div.pegination li.current a")
    if cur is not None:
        label = (cur.attributes.get("aria-label") or "") + " " + _text(cur)
        digits = [int(t) for t in label.replace("Page no.", " ").split() if t.isdigit()]
        cur_no = digits[0] if digits else None
    if cur_no is None:
        return False
    for a in tree.css("div.pegination a[href]"):
        tail = (a.attributes.get("href") or "").rstrip("/").rsplit("/", 1)[-1]
        if tail.isdigit() and int(tail) > cur_no:
            return True
    return False


def source_key(row: dict) -> str:
    basis = row["pdf_url"] or f"{row['title']}|{row['start']}"
    return "pdf-" + hashlib.sha256(basis.encode()).hexdigest()[:16]


class S3WaaSAdapter:
    family = "s3waas"

    def __init__(self, cfg: SourceConfig, http: HttpClient | None = None):
        self.cfg = cfg
        opts = cfg.options
        self.district = opts.get("district") or cfg.name
        self.window_days = int(opts.get("window_days", 90))
        self.max_pages = int(opts.get("max_pages", 3))
        self.authority = opts.get("authority") or f"District Administration, {self.district}"
        self.meta = AdapterMeta(
            source_code=cfg.id, source_name=cfg.name, portal_family="s3waas",
            base_url=cfg.base_url, region=cfg.region,
            crawl_delay=max(cfg.crawl_delay, 4.0),
            supports_documents=False, supports_results=False, supports_corrigenda=False,
            policy_notes="NIC S3WaaS district site; public notice tables only.",
        )
        self.http = http or HttpClient(min_delay=self.meta.crawl_delay)

    def fetch_outcome(self) -> FetchOutcome:
        outcome = FetchOutcome()
        seen: set[str] = set()
        cutoff = now_ist() - timedelta(days=self.window_days)
        now = now_ist()
        template_seen = False
        for path in LISTINGS:
            base = self.cfg.base_url.rstrip("/") + path
            for page in range(1, self.max_pages + 1):
                url = base if page == 1 else f"{base}page/{page}/"
                try:
                    res = self.http.get(url)
                except Exception as exc:  # noqa: BLE001
                    outcome.errors.append(f"{url}: {type(exc).__name__}: {exc}")
                    break
                if res.status_code == 404 and path == LISTINGS[0]:
                    outcome.notes.append(f"no active-tenders listing at {url} (404)")
                    break
                if res.status_code != 200:
                    outcome.errors.append(f"HTTP {res.status_code} for {url}")
                    break
                html = res.text
                template_seen = template_seen or is_s3waas(html)
                rows, has_next = parse_listing(html, url)
                if not rows:
                    break
                relevant = 0
                for r in rows:
                    in_window = r["start"] is None or r["start"] >= cutoff or (r["end"] is not None and r["end"] >= now)
                    if not in_window:
                        continue
                    relevant += 1
                    key = source_key(r)
                    if key in seen:
                        continue
                    seen.add(key)
                    outcome.tenders.append(build_tender(
                        source=self.meta.source_code, portal=self.meta.base_url, source_id=key,
                        title=r["title"], description=r["description"],
                        official_url=r["pdf_url"] or url, listing_url=url,
                        authority=self.authority, district=self.district,
                        start=r["start"], published=r["start"], closing=r["end"],
                        parser_version=PARSER_VERSION,
                    ))
                if relevant == 0 or not has_next:
                    break
        if not template_seen and not outcome.errors:
            outcome.degraded = True
            outcome.notes.append("S3WaaS template markers missing; layout may have changed")
        return outcome

    def fetch_incremental(self, *, since: datetime | None = None):
        yield from self.fetch_outcome().tenders

    def healthcheck(self) -> dict[str, object]:
        started = datetime.now()
        ok, error = False, None
        try:
            res = self.http.get(self.cfg.base_url.rstrip("/") + LISTINGS[1])
            if res.status_code != 200:
                error = f"HTTP {res.status_code}"
            elif is_s3waas(res.text):
                ok = True
            else:
                error = "S3WaaS template markers missing"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        return {
            "source": self.meta.source_code, "ok": ok, "error": error,
            "checked_at": started.astimezone().isoformat(),
            "latency_ms": int((datetime.now() - started).total_seconds() * 1000),
        }

    def close(self) -> None:
        self.http.close()
