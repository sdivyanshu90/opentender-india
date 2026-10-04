"""Fixture-driven adapter tests (spec #85): listings, details, malformed input."""

import json
from pathlib import Path

import pytest

from scrapers.adapters.gepnic import GePNICAdapter
from scrapers.core.http import detect_captcha
from scrapers.core.models import CanonicalTender
from scrapers.core.registry import SourceConfig

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def make_adapter(**overrides) -> GePNICAdapter:
    raw = {
        "id": "gepnic_test",
        "family": "gepnic",
        "name": "Test Portal",
        "base_url": "https://tenders.example.gov.in",
        "region": "Test State",
        "crawl_delay": 0.0,
        **overrides,
    }
    return GePNICAdapter(SourceConfig.from_dict(raw))


class TestListingParsing:
    def test_parses_three_rows(self):
        adapter = make_adapter()
        rows = adapter._parse_listing((FIXTURES / "gepnic" / "listing.html").read_text(), None)
        assert len(rows) == 3

    def test_row_fields(self):
        adapter = make_adapter()
        rows = adapter._parse_listing((FIXTURES / "gepnic" / "listing.html").read_text(), None)
        row = rows[0]
        assert row["tender_id"] == "2026_WRDS_1331127_1"
        assert row["reference_number"] == "WRD/EE/RMP/2026-27/088"
        assert "Solar Powered Micro Irrigation" in row["title"]
        assert "Water Resources Dept" in row["org_chain"]
        assert row["detail_href"].endswith("sp=SPlatpmyA1")

    def test_row_to_tender_stable_id(self):
        adapter = make_adapter()
        rows = adapter._parse_listing((FIXTURES / "gepnic" / "listing.html").read_text(), None)
        tender = adapter._row_to_tender(rows[0])
        assert isinstance(tender, CanonicalTender)
        assert tender.identity.source_tender_id == "2026_WRDS_1331127_1"
        assert tender.canonical_id == CanonicalTender.make_canonical_id("gepnic_test", "2026_WRDS_1331127_1")
        # deterministic across runs
        again = adapter._row_to_tender(rows[1])
        assert again.canonical_id != tender.canonical_id

    def test_malformed_html_does_not_raise(self):
        adapter = make_adapter()
        rows = adapter._parse_listing("<html><body><table><tr><td>broken", None)
        assert rows == []

    @pytest.mark.parametrize("encoding_case", ["utf-8"])
    def test_regional_text_preserved(self, encoding_case):
        html = (
            "<html><body><table><thead><tr><th>Sl.No</th></tr></thead>"
            "<tbody><tr><td>1</td><td>01-09-2026</td><td>10-09-2026</td>"
            "<td>11-09-2026</td><td>[2026_MUMH_9990001_1] जिल्हा रुग्णालय उभारणी काम</td>"
            "<td>Public Health Dept</td></tr></tbody></table></body></html>"
        )
        rows = make_adapter()._parse_listing(html, None)
        assert "जिल्हा रुग्णालय" in rows[0]["title"]


class TestHomeWidgetParsing:
    def _rows(self):
        return make_adapter()._parse_home_widget((FIXTURES / "gepnic" / "home.html").read_text())

    def test_parses_only_tender_rows(self):
        # the header row lives in a separate wrapper table and must be ignored
        assert len(self._rows()) == 3

    def test_row_fields(self):
        row = self._rows()[0]
        assert row["title"] == "ALIPARAMBA GP 160/26-27 KANDAMCHIRA PULIYAMPATTAKUNN PATHWAY CONCRETING"
        assert row["reference_number"] == "T2/AE/ALP/2026-27 dt. 3-10-2026"
        assert row["closing_raw"] == "13-Oct-2026 06:55 PM"
        assert row["detail_href"].startswith("https://tenders.example.gov.in/nicgep/app?component=%24DirectLink")

    def test_rows_without_tender_id_get_distinct_provisional_keys(self):
        adapter = make_adapter()
        tenders = [adapter._row_to_tender(r) for r in self._rows()]
        ids = {t.identity.source_tender_id for t in tenders}
        assert len(ids) == 3
        assert all(i.startswith("hash:") for i in ids)
        assert tenders[0].dates.bid_submission_end is not None

    def test_detail_tender_id_replaces_provisional_key(self, monkeypatch):
        from types import SimpleNamespace

        adapter = make_adapter()
        tender = adapter._row_to_tender(self._rows()[0])
        detail = "<table><tr><td>Tender ID</td><td>2026_LSGD_875715_6</td></tr></table>"
        monkeypatch.setattr(adapter._http, "get", lambda url: SimpleNamespace(status_code=200, text=detail))
        enriched = adapter._fetch_detail("https://tenders.example.gov.in/x", tender)
        assert enriched.identity.source_tender_id == "2026_LSGD_875715_6"
        assert enriched.canonical_id == CanonicalTender.make_canonical_id("gepnic_test", "2026_LSGD_875715_6")


class TestDetailParsing:
    def _detail_tree(self):
        from selectolax.lexbor import LexborHTMLParser as HTMLParser

        return HTMLParser((FIXTURES / "gepnic" / "detail.html").read_text())

    def test_detail_hydration(self):
        adapter = make_adapter()
        listing_rows = adapter._parse_listing(
            (FIXTURES / "gepnic" / "listing.html").read_text(), None)
        adapter._row_to_tender(listing_rows[0])
        tree = self._detail_tree()
        docs = adapter._parse_documents(tree)
        corr = adapter._parse_corrigenda_links(tree)
        assert len(docs) == 2  # NIT + BOQ links detected; captcha interstitial not followed here
        assert len(corr) == 1

    def test_label_map_coverage(self):
        # every mapped path must resolve against the model
        from scrapers.adapters.gepnic import _LABEL_MAP
        adapter = make_adapter()
        tender = adapter._row_to_tender({"title": "x", "closing_raw": "05-Sep-2026 03:00 PM"})
        for paths in _LABEL_MAP.values():
            for path in paths:
                if path is None:
                    continue
                section, key = path.split(".", 1)
                obj = getattr(tender, section)
                assert hasattr(obj, key), f"bad label-map target {path}"


class TestCaptchaGuard:
    def test_detect(self):
        assert detect_captcha('Please fill the Captcha <input name="captchaText">')
        assert detect_captcha("PROVIDE CAPTCHA and click search")
        assert not detect_captcha("<html>normal page</html>")


class TestGemAdapter:
    def _docs(self):
        return json.loads((FIXTURES / "gem" / "all-bids-data.json").read_text())["response"]["response"]["docs"]

    def test_doc_to_tender(self):
        from scrapers.adapters.gem import GemAdapter
        cfg = SourceConfig.from_dict({
            "id": "gem_bids", "family": "gem", "name": "GeM",
            "base_url": "https://bidplus.gem.gov.in", "region": "India",
            "crawl_delay": 0.0,
        })
        adapter = GemAdapter(cfg)
        t = adapter._doc_to_tender(self._docs()[0])
        assert t.identity.tender_number == "GEM/2026/B/7800616"
        assert t.procurement.title.startswith("Supply and installation of rooftop solar")
        assert t.status == "active"
        ra = adapter._doc_to_tender(self._docs()[1])
        assert ra.procurement.tender_type == "ra"

    def test_solr_multivalued_doc(self):
        # live API shape (Oct 2026): every field is a single-element list, no bbt_title
        from scrapers.adapters.gem import GemAdapter
        cfg = SourceConfig.from_dict({
            "id": "gem_bids", "family": "gem", "name": "GeM",
            "base_url": "https://bidplus.gem.gov.in", "region": "India",
            "crawl_delay": 0.0,
        })
        doc = json.loads((FIXTURES / "gem" / "all-bids-data-solr.json").read_text())[0]
        t = GemAdapter(cfg)._doc_to_tender(doc)
        assert t.identity.tender_number == "GEM/2026/B/7845020"
        assert t.procurement.title.startswith("Repair and Overhauling Service")
        assert t.procurement.category.startswith("Repair and Overhauling Service")
        assert t.organization.ministry == "Ministry of Defence"
        assert t.dates.bid_submission_end is not None
        assert t.status == "active"

    def test_epoch_dates(self):
        from scrapers.adapters.gem import _gem_ts
        iso = _gem_ts(1755512400000)
        assert iso.startswith("2025") or iso.startswith("202")


class TestStoreAndDiff:
    def test_upsert_and_change_detection(self, tmp_path):
        from scrapers.core.store import TenderStore

        store = TenderStore(tmp_path)
        base = {
            "canonical_id": "a" * 24,
            "identity": {"source": "s", "source_portal": "https://x", "source_tender_id": "1"},
            "procurement": {"title": "Original title"},
            "financial": {"estimated_value": 1000000},
            "provenance": {
                "official_source_url": "https://x/t/1",
                "scraped_at": "2026-08-20T10:00:00+05:30",
                "first_seen_at": "2026-08-20T10:00:00+05:30",
                "last_seen_at": "2026-08-20T10:00:00+05:30",
                "parser_version": "test",
                "content_hash": "sha256:" + "0" * 64,
            },
        }
        t1 = CanonicalTender.model_validate(base)
        merged, changes, is_new = store.upsert(t1)
        assert is_new
        t2 = t1.model_copy(deep=True)
        t2.financial.estimated_value = 2_000_000
        t2.dates.bid_submission_end = __import__("datetime").datetime(2026, 9, 30, tzinfo=__import__("scrapers.core.dates", fromlist=["IST"]).IST)
        merged2, changes2, is_new2 = store.upsert(t2)
        assert not is_new2
        fields = {c.field for c in changes2}
        assert "financial.estimated_value" in fields
        assert any(c.field == "dates.bid_submission_end" for c in changes2)
        # persisted roundtrip
        loaded = store.existing("a" * 24)
        assert loaded.financial.estimated_value == 2_000_000


class TestSourceHealth:
    def test_status_file_roundtrip_across_runs(self, tmp_path):
        from scrapers.core.health import SourceHealthTracker

        path = tmp_path / "sources.json"
        first = SourceHealthTracker(path)
        first.record("gepnic_x", ok=True, discovered=10, new_tenders=10, changed_tenders=0)
        first.write()
        # the next day's run must load what the previous run wrote
        second = SourceHealthTracker(path)
        second.record("gepnic_x", ok=True, discovered=8, new_tenders=1, changed_tenders=2)
        second.write()
        snap = json.loads(path.read_text())
        assert snap["sources"]["gepnic_x"]["discovered_last_run"] == 8
        assert snap["records"]["gepnic_x"]["discovered_baseline"] == [10, 8]

    def test_loads_legacy_snapshot_and_recovers_from_captcha_status(self, tmp_path):
        from scrapers.core.health import SourceHealthTracker

        path = tmp_path / "sources.json"
        path.write_text(json.dumps({
            "generated_at": "2026-10-03T00:00:00+05:30",
            "sources": {"gepnic_x": {"status": "CAPTCHA_LIMITED", "last_success": None}},
        }))
        tracker = SourceHealthTracker(path)
        tracker.record("gepnic_x", ok=True, discovered=10, new_tenders=10, changed_tenders=0)
        tracker.write()
        assert json.loads(path.read_text())["sources"]["gepnic_x"]["status"] == "ACTIVE"
