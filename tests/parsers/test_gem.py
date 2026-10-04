"""GeM adapter: pagination, field mapping, deep links (offline, fixture based)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scrapers.adapters.gem import GemAdapter, _gem_ts, _unwrap_solr
from scrapers.core.registry import SourceConfig

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "gem"


def _adapter(**opts) -> GemAdapter:
    cfg = SourceConfig.from_dict({
        "id": "gem_bids", "family": "gem", "name": "GeM",
        "base_url": "https://bidplus.gem.gov.in", "region": "India",
        "crawl_delay": 0.0, "max_pages": 5, **opts,
    })
    return GemAdapter(cfg)


def _docs() -> list[dict]:
    return json.loads((FIXTURES / "all-bids-data-solr.json").read_text())


def _mk(n: int, **extra) -> dict:
    d = {"b_id": [1000 + n], "b_bid_number": [f"GEM/2026/B/{n}"], "b_category_name": [f"Item {n}"],
         "b_bid_type": [1], "b_buyer_status": [0], "b_eval_type": [0],
         "final_start_date_sort": ["2026-10-01T10:00:00Z"], "final_end_date_sort": ["2026-10-09T09:00:00Z"]}
    d.update(extra)
    return d


class FakePages:
    """Stands in for _get_csrf_token/_fetch_page; records requested pages."""

    def __init__(self, pages: list[list[dict]], total=None, fail_at=None):
        self.pages, self.total, self.fail_at, self.calls = pages, total, fail_at, []

    def install(self, ad: GemAdapter) -> None:
        ad._get_csrf_token = lambda outcome: "t" * 32

        def fetch(page, token, outcome):
            self.calls.append(page)
            if page == self.fail_at:
                outcome.errors.append("boom")
                return [], None, True
            docs = self.pages[page - 1] if page <= len(self.pages) else []
            return docs, self.total, False

        ad._fetch_page = fetch


def test_stops_on_empty_page():
    ad = _adapter(max_pages=10)
    fp = FakePages([[_mk(i) for i in range(10)], [_mk(i) for i in range(10, 20)]])
    fp.install(ad)
    out = ad.fetch_outcome()
    assert len(out.tenders) == 20 and fp.calls == [1, 2, 3]


def test_stops_on_short_last_page_and_numfound():
    ad = _adapter(max_pages=10)
    fp = FakePages([[_mk(i) for i in range(10)], [_mk(i) for i in range(10, 14)]])
    fp.install(ad)
    assert len(ad.fetch_outcome().tenders) == 14 and fp.calls == [1, 2]
    ad = _adapter(max_pages=10)
    fp = FakePages([[_mk(i) for i in range(10)]] * 5, total=20)
    fp.install(ad)
    ad.fetch_outcome()
    assert fp.calls == [1, 2] or fp.calls == [1]  # never beyond numFound


def test_stops_when_pagination_does_not_advance():
    ad = _adapter(max_pages=10)
    same = [_mk(i) for i in range(10)]
    fp = FakePages([same, same, same])
    fp.install(ad)
    out = ad.fetch_outcome()
    assert len(out.tenders) == 10 and fp.calls == [1, 2]


def test_stops_on_error_and_keeps_earlier_pages():
    ad = _adapter(max_pages=10)
    fp = FakePages([[_mk(i) for i in range(10)], [_mk(i) for i in range(10, 20)]], fail_at=2)
    fp.install(ad)
    out = ad.fetch_outcome()
    assert len(out.tenders) == 10 and out.errors and fp.calls == [1, 2]


def test_respects_max_pages_cap():
    ad = _adapter(max_pages=2)
    fp = FakePages([[_mk(i + 10 * p) for i in range(10)] for p in range(5)])
    fp.install(ad)
    assert len(ad.fetch_outcome().tenders) == 20 and fp.calls == [1, 2]


def test_newest_first_sort_default_and_payload():
    assert _adapter().sort == "Bid-Start-Date-Latest"
    ad = _adapter()
    sent = {}

    class R:
        status_code = 200
        text = json.dumps({"code": 200, "response": {"response": {"numFound": 1, "docs": [_mk(1)]}}})

    def post(url, data=None, headers=None):
        sent.update(json.loads(data["payload"]))
        return R()

    ad._http.post = post
    class Outcome:
        errors: list = []
        notes: list = []
        degraded = False

    docs, found, err = ad._fetch_page(2, "t", Outcome())
    assert sent["page"] == 2 and sent["filter"]["sort"] == "Bid-Start-Date-Latest"
    assert found == 1 and len(docs) == 1 and not err


def test_blocked_network_fails_fast_with_clear_message():
    ad = _adapter()

    def boom(url, **kw):
        raise httpx.ConnectError("refused")

    ad._http.get = boom
    out = ad.fetch_outcome()
    assert out.tenders == [] and "blocked from this network" in out.errors[0]


def test_field_mapping_and_deep_link():
    ad = _adapter()
    t = ad._doc_to_tender(_docs()[0])
    assert t.identity.tender_number == "GEM/2026/B/7845020"
    assert t.provenance.official_source_url == "https://bidplus.gem.gov.in/showbidDocument/9673281"
    assert t.provenance.source_listing_url == "https://bidplus.gem.gov.in/all-bids"
    assert t.documents[0].source_url == t.provenance.official_source_url
    assert t.procurement.tender_type == "open"
    assert t.procurement.procurement_type == "services"
    assert t.organization.ministry == "Ministry of Defence"
    assert "Quantity: 1" in t.procurement.description
    assert t.status == "active"


def test_dates_are_ist_wall_clock():
    t = _adapter()._doc_to_tender(_docs()[0])
    assert t.dates.bid_submission_end.isoformat() == "2026-10-05T09:00:00+05:30"
    assert _gem_ts("2026-10-05T09:00:00Z") == "2026-10-05T09:00:00"


def test_reverse_auction_mapping():
    ra = _mk(7, b_bid_type=[2], b_bid_number=["GEM/2026/R/7"], b_id_parent=[555],
             b_bid_number_parent=["GEM/2026/B/55"], b_total_quantity=[129328])
    t = _adapter()._doc_to_tender(ra)
    assert t.provenance.official_source_url.endswith("/showradocumentPdf/1007")
    assert t.procurement.tender_type == "ra" and t.procurement.procurement_type == "auction"
    assert t.identity.reference_number == "GEM/2026/B/55"
    assert t.documents[1].source_url.endswith("/showbidDocument/555")
    assert "Quantity: 129328" in t.procurement.description
    direct = _adapter().doc_url(_unwrap_solr(_mk(8, b_bid_type=[5])))
    assert direct.endswith("/showdirectradocumentPdf/1008")


def test_missing_values_are_not_invented():
    t = _adapter()._doc_to_tender({"b_bid_number": ["GEM/2026/B/9"]})
    assert t.procurement.description is None and t.dates.bid_submission_end is None
    assert t.provenance.official_source_url.endswith("/bidlists")
    assert t.documents == []


@pytest.mark.parametrize("bad", [None, {}, {"foo": 1}])
def test_unusable_docs_skipped(bad):
    assert _adapter()._doc_to_tender(bad or {}) is None


def test_live_ra_fixture_maps():
    docs = json.loads((FIXTURES / "all-bids-data-solr-ra.json").read_text())
    t = _adapter()._doc_to_tender(docs[0])
    assert t.procurement.tender_type == "ra"
    assert t.provenance.official_source_url.endswith(f"/showradocumentPdf/{docs[0]['b_id'][0]}")
    assert t.identity.reference_number == docs[0]["b_bid_number_parent"][0]
