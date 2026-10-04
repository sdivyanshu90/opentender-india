"""CPPP national state-tenders listing adapter.

https://eprocure.gov.in/cppp/statetendersclosingbydays/byday/byYYYY-MM-DD lists
every state/UT tender closing that day (10 rows/page, "Total Tenders : N").
Listing pages are server-rendered and open; the detail pages are CAPTCHA-gated
and are never fetched, so rows are listing-level only (title, reference,
Tender ID, dates, state). There is no state filter: states_include only
filters rows after they are paged through.

Columns: S.No | e-Published | Closing | Opening | Title/Ref.No./Tender Id | State Name | Corrigendum
The title cell is ``<a>Title</a>/Ref/TenderId``; the State Name column also
carries central PSU/ministry names, which are kept as the authority instead.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from urllib.parse import quote

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from scrapers.core.adapter import AdapterMeta, FetchOutcome
from scrapers.core.dates import IST, parse_datetime
from scrapers.core.geo_data import STATE_NAMES
from scrapers.core.http import HttpClient, detect_captcha
from scrapers.core.models import CanonicalTender, ProvenanceInfo, TenderIdentity
from scrapers.core.registry import SourceConfig
from scrapers.core.textutil import clean_text

log = logging.getLogger("opentender.cppp_state")

DAY_PATH = "/cppp/statetendersclosingbydays/byday/by"
ROWS_PER_PAGE = 10
TOTAL_RE = re.compile(r"Total Tenders\s*:\s*(\d+)", re.I)
GEPNIC_ID_RE = re.compile(r"^\d{4}_[A-Z0-9]+_\d+_\d+$")

_STATE_LOOKUP: dict[str, str] = {}
for _canon, _names in STATE_NAMES.items():
    _STATE_LOOKUP[_canon.lower()] = _canon
    for _n in _names:
        # only whole-state aliases; skip bare city/region hints such as "daman", "andaman"
        if _n.lower() in {"kashmir", "daman", "andaman", "nicobar", "silvassa", "andhra", "arunachal", "himachal"}:
            continue
        _STATE_LOOKUP[_n.lower()] = _canon


def normalise_state(raw: str | None) -> str | None:
    """Map a State Name cell to our canonical state/UT, or None if it is not one
    (the column also holds central PSU / ministry names)."""
    if not raw:
        return None
    key = re.sub(r"\s+", " ", raw.lower().replace("&", " and ")).strip()
    key = re.sub(r"[.,]", "", key)
    key = re.sub(r"\s*\(?\bu\.?t\.?\)?$", "", key).strip()  # "Ladakh UT"
    key = re.sub(r"\bislands?$", "islands", key)  # CPPP spells "Andaman and Nicobar Island"
    return _STATE_LOOKUP.get(key)


def day_url(base_url: str, day: date) -> str:
    return f"{base_url}{DAY_PATH}{day.isoformat()}"


def page_url(day_base: str, page: int) -> str:
    """CPPP pagination: ?url=<urlquoted base64 of "<base>?page=N">, page 0-based."""
    token = base64.b64encode(f"{day_base}?page={page}".encode()).decode()
    return f"{day_base}?url={quote(token)}"


def parse_total(html: str) -> int | None:
    m = TOTAL_RE.search(HTMLParser(html).text(separator=" "))
    return int(m.group(1)) if m else None


def split_title_cell(title: str | None, tail: str) -> tuple[str | None, str | None, str | None]:
    """(title, reference, tender_id) from the link text and the "/Ref/ID" tail."""
    parts = [p.strip() for p in tail.split("/") if p.strip()]
    tender_id = parts[-1] if parts else None
    ref_parts = parts[:-1]
    if title is None and ref_parts:
        title = ref_parts.pop(0)
    reference = "/".join(ref_parts) or None
    return clean_text(title), clean_text(reference, max_len=200), tender_id


def parse_rows(html: str) -> list[dict]:
    rows: list[dict] = []
    for tr in HTMLParser(html).css("table tr"):
        tds = tr.css("td")
        if len(tds) < 6:
            continue
        cells = [clean_text(td.text(separator=" ", deep=True), max_len=2000) or "" for td in tds]
        if not re.fullmatch(r"\d+\.?", cells[0]):
            continue
        link = tds[4].css_first("a")
        link_text = clean_text(link.text(separator=" ", deep=True)) if link else None
        full = cells[4]
        if link_text is None:
            title, ref, tid = split_title_cell(None, full)
        else:
            title, ref, tid = split_title_cell(link_text, full.replace(link_text, "", 1))
        rows.append(
            {
                "published_raw": cells[1],
                "closing_raw": cells[2],
                "opening_raw": cells[3],
                "title": title,
                "reference_number": ref,
                "tender_id": tid,
                "state_raw": cells[5],
                "corrigendum": cells[6] if len(cells) > 6 else "",
            }
        )
    return rows


def plan_pages(totals: dict[date, int], budget: int, *, rotate: int = 0) -> dict[date, list[int]]:
    """Spread `budget` extra page reads (page 0 of each day is already read)
    proportionally to each day's remaining pages, evenly strided over the day
    so state diversity is kept when a day cannot be read in full."""
    remaining = {d: max(0, (t - 1) // ROWS_PER_PAGE) for d, t in totals.items()}
    total_rem = sum(remaining.values())
    plan: dict[date, list[int]] = {}
    if total_rem == 0 or budget <= 0:
        return {d: [] for d in totals}
    for d in sorted(totals):
        rem = remaining[d]
        quota = rem if budget >= total_rem else int(budget * rem / total_rem)
        if quota >= rem:
            plan[d] = list(range(1, rem + 1))
        elif quota <= 0:
            plan[d] = []
        else:
            stride = rem / quota
            off = rotate % max(1, int(stride)) if stride >= 1 else 0
            plan[d] = sorted({min(rem, 1 + int(i * stride) + off) for i in range(quota)})
    return plan


class CpppStateAdapter:
    family = "cppp_state"

    def __init__(self, cfg: SourceConfig, http: HttpClient | None = None):
        self.cfg = cfg
        opts = cfg.options
        self.days_ahead = int(opts.get("days_ahead", 45))
        self.max_pages = int(opts.get("max_pages_per_run", 700))
        self.states_include = {s for s in (opts.get("states_include") or [])} or None
        self.skip_states = set(opts.get("skip_states") or [])
        self.meta = AdapterMeta(
            source_code=cfg.id,
            source_name=cfg.name,
            portal_family="cppp_state",
            base_url=cfg.base_url,
            region=cfg.region,
            crawl_delay=cfg.crawl_delay,
            supports_corrigenda=False,
            policy_notes=cfg.policy_notes,
        )
        self._http = http or HttpClient(min_delay=self.meta.crawl_delay)

    # -- public API ------------------------------------------------------------

    def fetch_incremental(self, *, since: datetime | None = None) -> Iterator[CanonicalTender]:
        yield from self.fetch_outcome().tenders

    def healthcheck(self) -> dict[str, object]:
        started = datetime.now()
        ok, error = False, None
        try:
            html = self._http.get(day_url(self.cfg.base_url, datetime.now(tz=IST).date() + timedelta(days=1))).text
            if detect_captcha(html) and not parse_rows(html):
                error = "captcha on listing"
            elif TOTAL_RE.search(html):
                ok = True
            else:
                error = "expected CPPP listing markers missing"
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

    def fetch_outcome(self, *, today: date | None = None) -> FetchOutcome:
        outcome = FetchOutcome()
        today = today or datetime.now(tz=IST).date()
        days = [today + timedelta(days=k) for k in range(1, self.days_ahead + 1)]
        rows_by_day: dict[date, list[dict]] = {}
        totals: dict[date, int] = {}
        pages_read = 0
        failures = 0
        stopped = False

        def get(url: str):
            """One polite page read; returns html, or None to skip/stop (flags set on outcome)."""
            nonlocal pages_read, failures, stopped
            pages_read += 1  # failed attempts cost a request too
            try:
                res = self._http.get(url)
            except Exception as exc:  # noqa: BLE001 - one dropped connection must not lose the run
                failures += 1
                outcome.notes.append(f"{url[-60:]}: {type(exc).__name__}, skipped")
                if failures >= 3:
                    outcome.notes.append("3 consecutive page failures, crawl stopped")
                    stopped = True
                return None
            failures = 0
            html = res.text
            if res.status_code != 200:
                outcome.notes.append(f"HTTP {res.status_code} for {url[-60:]}, crawl stopped")
                stopped = True
                return None
            if detect_captcha(html) and not parse_rows(html):
                outcome.captcha_hit = True
                outcome.notes.append("listing is CAPTCHA-gated; stopped politely")
                stopped = True
                return None
            return html

        # phase 1: page 0 of every day (also yields that day's total)
        for d in days:
            if stopped or pages_read >= self.max_pages:
                break
            html = get(day_url(self.cfg.base_url, d))
            if html is None:
                continue
            totals[d] = parse_total(html) or 0
            rows_by_day[d] = parse_rows(html)
            if totals[d] and not rows_by_day[d]:
                outcome.notes.append(f"{d}: total {totals[d]} but no rows parsed")
                outcome.degraded = True

        # phase 2: spread the remaining budget proportionally over the days
        planned = 0
        if not stopped:
            plan = plan_pages(totals, self.max_pages - pages_read, rotate=today.toordinal())
            planned = sum(len(v) for v in plan.values())
            for d in sorted(plan):
                base = day_url(self.cfg.base_url, d)
                for p in plan[d]:
                    if stopped:
                        break
                    html = get(page_url(base, p))
                    if html is not None:
                        rows_by_day[d] += parse_rows(html)
                if stopped:
                    break

        advertised = sum(totals.values())
        total_pages = sum(max(1, -(-t // ROWS_PER_PAGE)) for t in totals.values())
        seen: set[str] = set()
        skipped_state = 0
        corrigenda = 0
        for d in sorted(rows_by_day):
            base = day_url(self.cfg.base_url, d)
            for row in rows_by_day[d]:
                tender = self._row_to_tender(row, base)
                if tender is None:
                    outcome.errors.append(f"unparseable row: {(row.get('title') or '')[:80]}")
                    continue
                key = tender.identity.source_tender_id
                if key in seen:
                    continue
                state = tender.geography.state
                if (self.states_include and state not in self.states_include) or (state in self.skip_states):
                    skipped_state += 1
                    continue
                seen.add(key)
                if row.get("corrigendum", "--") not in ("", "--", "-"):
                    corrigenda += 1
                outcome.tenders.append(tender)
        outcome.notes.append(
            f"cppp_state: read {pages_read} pages (planned {planned} extra) across {len(totals)}/{len(days)} days; "
            f"coverage {len(seen) + skipped_state} of {advertised} advertised rows "
            f"({pages_read}/{total_pages} pages); kept {len(seen)}, filtered by state {skipped_state}; "
            f"{corrigenda} rows list a corrigendum"
        )
        if not rows_by_day and not outcome.captcha_hit and not outcome.errors:
            outcome.degraded = True
        return outcome

    # -- row -> canonical ---------------------------------------------------------

    def _row_to_tender(self, row: dict, listing_url: str) -> CanonicalTender | None:
        title, tender_id = row.get("title"), row.get("tender_id")
        if not title and not tender_id:
            return None
        now = datetime.now(tz=IST)
        state = normalise_state(row.get("state_raw"))
        state_raw = row.get("state_raw") or None
        if tender_id and GEPNIC_ID_RE.match(tender_id):
            source_id = tender_id  # stable across sources: matches our direct GePNIC crawls
        elif tender_id:
            source_id = f"{(state or state_raw or 'x').lower().replace(' ', '-')}:{tender_id}"
        else:
            digest = hashlib.sha256(f"{title}|{row.get('reference_number') or ''}".encode()).hexdigest()[:16]
            source_id = f"hash:{digest}"
        closing = parse_datetime(row.get("closing_raw"))
        status = "active" if (closing and closing > now) else "closed" if closing else "unknown"
        provenance = ProvenanceInfo(
            official_source_url=listing_url,
            source_listing_url=listing_url,
            scraped_at=now,
            first_seen_at=now,
            last_seen_at=now,
            parser_version="cppp-state-1.0.0",
            content_hash="pending",
        )
        tender = CanonicalTender(
            canonical_id=CanonicalTender.make_canonical_id(self.meta.source_code, source_id),
            identity=TenderIdentity(
                source=self.meta.source_code,
                source_portal=self.meta.base_url,
                source_tender_id=source_id,
                reference_number=row.get("reference_number"),
            ),
            procurement={"title": title},
            # the State Name column holds PSU/ministry names for central tenders
            organization={"authority": None if state else clean_text(state_raw, max_len=500)},
            geography={"state": state},
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
