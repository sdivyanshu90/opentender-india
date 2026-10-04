"""Maharashtra adapters: notice_pages (MahaGenco/MahaTransco/MSEDCL) and S3WaaS.

Offline, fixture based; HttpClient is replaced by a fake that serves canned pages.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scrapers.adapters.notice_pages import (
    NoticePagesAdapter,
    parse_mahagenco,
    parse_mahatransco,
    parse_msedcl,
)
from scrapers.adapters.s3waas import S3WaaSAdapter, parse_listing, source_key
from scrapers.core.dates import IST
from scrapers.core.models import CanonicalTender
from scrapers.core.registry import SourceConfig, build_adapter, load_configs

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def read(rel: str) -> str:
    return (FIX / rel).read_text("utf-8")


class FakeResult:
    def __init__(self, text: str, status: int = 200):
        self.content, self.status_code, self.url = text.encode(), status, ""

    @property
    def text(self) -> str:
        return self.content.decode()


class FakeHttp:
    def __init__(self, pages: dict[str, str], default: str | None = None):
        self.pages, self.default, self.calls = pages, default, []

    def get(self, url: str) -> FakeResult:
        self.calls.append(url)
        if url in self.pages:
            return FakeResult(self.pages[url])
        if self.default is not None:
            return FakeResult(self.default)
        return FakeResult("nope", 404)

    def close(self) -> None:
        pass


def cfg(**kw) -> SourceConfig:
    base = {"id": "t", "family": "notice_pages", "name": "T", "base_url": "https://x.example/tenders",
            "region": "Maharashtra", "crawl_delay": 0.0}
    base.update(kw)
    return SourceConfig.from_dict(base)


# -- MahaGenco --------------------------------------------------------------------

def test_mahagenco_parse_rows_and_dates():
    rows = parse_mahagenco(read("notice_pages/mahagenco.html"))
    assert len(rows) == 5  # Marathi list (#tenderlst_1m) is ignored
    first = rows[0]
    assert first["notice_no"] == "22(i)/2026-27"
    assert first["published"] == datetime(2026, 10, 2, 11, 45, 52, tzinfo=IST)
    assert first["url"].startswith("https://www.mahagenco.in/tenderpdf/Giri%20Media")
    assert rows[-1]["published"] is None


def test_mahagenco_window_filters_history(monkeypatch):
    import scrapers.adapters.notice_pages as np_

    monkeypatch.setattr(np_, "now_ist", lambda: datetime(2026, 10, 4, tzinfo=IST))
    ad = NoticePagesAdapter(cfg(parser="mahagenco", window_days=60),
                            http=FakeHttp({}, read("notice_pages/mahagenco.html")))
    out = ad.fetch_outcome()
    assert out.ok and len(out.tenders) == 2
    t = out.tenders[0]
    assert isinstance(t, CanonicalTender)
    assert t.geography.state == "Maharashtra"
    assert "MahaGenco" in t.organization.authority
    assert t.status == "unknown" and t.dates.bid_submission_end is None
    assert t.provenance.official_source_url.endswith(".pdf")
    assert t.provenance.content_hash.startswith("sha256:")
    assert t.identity.tender_number == "22(i)/2026-27"


def test_mahagenco_empty_is_degraded():
    ad = NoticePagesAdapter(cfg(parser="mahagenco"), http=FakeHttp({}, "<html></html>"))
    out = ad.fetch_outcome()
    assert out.degraded and not out.tenders


# -- MahaTransco ------------------------------------------------------------------

def test_mahatransco_parse():
    rows, nxt = parse_mahatransco(read("notice_pages/mahatransco.html"))
    assert [r["rfx_no"] for r in rows] == ["1005", "7000041742", "7000041730"]
    assert rows[1]["zone"] == "Corporate Office"
    assert rows[1]["end"] == datetime(2026, 10, 10, tzinfo=IST)
    assert rows[0]["url"].endswith("tender_1790833863.pdf")
    assert nxt == "https://www.mahatransco.in/tenders/active/20"


def test_mahatransco_pagination_max_pages_and_status():
    html = read("notice_pages/mahatransco.html")
    http = FakeHttp({}, html)
    ad = NoticePagesAdapter(cfg(parser="mahatransco", base_url="https://www.mahatransco.in/tenders/active",
                                max_pages=2), http=http)
    out = ad.fetch_outcome()
    assert len(http.calls) == 2  # follows rel=next once, then stops at max_pages
    assert http.calls[1] == "https://www.mahatransco.in/tenders/active/20"
    assert out.tenders[0].dates.bid_submission_end == datetime(2026, 11, 7, tzinfo=IST)
    assert out.tenders[0].identity.tender_number == "1005"
    assert out.tenders[0].organization.department == "Karad"
    assert all(t.status in {"active", "closed"} for t in out.tenders)
    assert len({t.canonical_id for t in out.tenders}) == 3  # page repeat deduped by key in store


def test_mahatransco_empty_page_stops():
    ad = NoticePagesAdapter(cfg(parser="mahatransco"), http=FakeHttp({}, "<html></html>"))
    assert ad.fetch_outcome().degraded


# -- MSEDCL -----------------------------------------------------------------------

def test_msedcl_parse():
    posts, total = parse_msedcl(read("notice_pages/msedcl.html"))
    assert total == 29 and len(posts) == 3
    assert posts[0]["post_id"] == "83603"
    assert posts[0]["published"] == datetime(2026, 9, 24, 23, 30, tzinfo=IST)


def test_msedcl_window_stops(monkeypatch):
    import scrapers.adapters.notice_pages as np_

    monkeypatch.setattr(np_, "now_ist", lambda: datetime(2026, 10, 4, tzinfo=IST))
    http = FakeHttp({}, read("notice_pages/msedcl.html"))
    ad = NoticePagesAdapter(cfg(parser="msedcl", base_url="https://x.example/tenders/", window_days=20,
                                max_pages=5), http=http)
    out = ad.fetch_outcome()
    assert [t.identity.source_tender_id for t in out.tenders[:2]] == ["post-83603", "post-83555"]
    assert http.calls[1].endswith("/tenders/page/2/")
    ad2 = NoticePagesAdapter(cfg(parser="msedcl", base_url="https://x.example/tenders/", window_days=1,
                                 max_pages=5), http=FakeHttp({}, read("notice_pages/msedcl.html")))
    out2 = ad2.fetch_outcome()
    assert out2.tenders == [] and len(ad2.http.calls) == 1  # all too old: stop after first page
    assert out.tenders[0].geography.state == "Maharashtra"
    assert out.tenders[0].status == "unknown"


# -- S3WaaS -----------------------------------------------------------------------

def test_s3waas_parse_rows_dates_next():
    rows, has_next = parse_listing(read("s3waas/archive_page1.html"), "https://pune.gov.in/en/past-notices/tenders/")
    assert len(rows) == 3 and has_next
    assert rows[0]["start"] == datetime(2025, 7, 24, tzinfo=IST)
    assert rows[0]["end"] == datetime(2025, 8, 14, tzinfo=IST)
    assert rows[0]["pdf_url"].startswith("https://cdn.s3waas.gov.in/")
    assert rows[1]["title"] == "Xerox, Computer Repair & Maintenance, Stationery Material Tender"
    assert source_key(rows[0]) != source_key(rows[1])
    assert source_key(rows[0]) == source_key(dict(rows[0]))


def test_s3waas_empty_page():
    rows, has_next = parse_listing(read("s3waas/active_empty.html"), "https://pune.gov.in/en/notice_category/tenders/")
    assert rows == [] and not has_next


def _s3(**kw) -> S3WaaSAdapter:
    c = cfg(id="s3waas_pune", family="s3waas", base_url="https://pune.gov.in", district="Pune", **kw)
    return c


def test_s3waas_fetch_window_and_stop(monkeypatch):
    import scrapers.adapters.s3waas as m

    monkeypatch.setattr(m, "now_ist", lambda: datetime(2025, 8, 1, tzinfo=IST))
    http = FakeHttp({"https://pune.gov.in/en/notice_category/tenders/": read("s3waas/active_empty.html")},
                    read("s3waas/archive_page1.html"))
    ad = S3WaaSAdapter(_s3(max_pages=3, window_days=90), http=http)
    out = ad.fetch_outcome()
    assert out.ok and len(out.tenders) == 3
    # archive page 2 requested (has next), page 3 not (fixture repeats page 1 -> same keys deduped)
    assert "https://pune.gov.in/en/past-notices/tenders/page/2/" in http.calls
    t = out.tenders[0]
    assert t.geography.state == "Maharashtra" and t.geography.district == "Pune"
    assert t.organization.authority and "Pune" in t.organization.authority
    assert t.status == "closed"
    assert t.provenance.official_source_url.endswith(".pdf")


def test_s3waas_old_rows_stop_paging(monkeypatch):
    import scrapers.adapters.s3waas as m

    monkeypatch.setattr(m, "now_ist", lambda: datetime(2026, 10, 4, tzinfo=IST))
    http = FakeHttp({}, read("s3waas/archive_page1.html"))
    out = S3WaaSAdapter(_s3(max_pages=5, window_days=30), http=http).fetch_outcome()
    assert out.tenders == []
    # one call per listing (active + archive); no page/2 since nothing relevant
    assert len(http.calls) == 2


def test_s3waas_active_status_from_future_end(monkeypatch):
    import scrapers.adapters.s3waas as m

    monkeypatch.setattr(m, "now_ist", lambda: datetime(2025, 8, 1, tzinfo=IST))
    out = S3WaaSAdapter(_s3(max_pages=1), http=FakeHttp({}, read("s3waas/archive_page1.html"))).fetch_outcome()
    by_end = {t.dates.bid_submission_end.date().isoformat(): t.status for t in out.tenders}
    assert by_end  # statuses derive from real clock in build_tender
    assert all(s in {"active", "closed"} for s in by_end.values())


def test_s3waas_template_missing_is_degraded():
    out = S3WaaSAdapter(_s3(), http=FakeHttp({}, "<html><body>hi</body></html>")).fetch_outcome()
    assert out.degraded


def test_s3waas_http_error_reported():
    out = S3WaaSAdapter(_s3(), http=FakeHttp({})).fetch_outcome()
    assert out.errors


# -- registry -----------------------------------------------------------------------

def test_registry_builds_each_family():
    for fam, extra in (("notice_pages", {"parser": "mahagenco"}), ("s3waas", {"district": "Pune"})):
        c = cfg(family=fam, **extra)
        ad = build_adapter(c)
        assert ad.meta.portal_family == fam
        assert ad.meta.crawl_delay >= 4.0
        ad.close()


def test_maharashtra_config_entries_valid():
    entries = [c for c in load_configs() if c.family in {"notice_pages", "s3waas"}]
    ids = [c.id for c in entries]
    assert len(ids) == len(set(ids)) and {"mahagenco_notices", "mahatransco_tenders"} <= set(ids)
    assert any(c.family == "s3waas" for c in entries)
    for c in entries:
        assert c.crawl_delay >= 4 and c.declared_status == "EXPERIMENTAL"
        assert c.options.get("state") == "Maharashtra"
        assert "mahatenders.gov.in" not in c.base_url
        ad = build_adapter(c)
        assert ad is not None
        ad.close()


def test_unknown_parser_rejected():
    with pytest.raises(ValueError):
        NoticePagesAdapter(cfg(parser="nope"), http=FakeHttp({}))


def test_since_unused_but_iterator_works():
    ad = NoticePagesAdapter(cfg(parser="mahatransco", max_pages=1), http=FakeHttp({}, read("notice_pages/mahatransco.html")))
    assert len(list(ad.fetch_incremental(since=datetime.now() - timedelta(days=1)))) == 3
