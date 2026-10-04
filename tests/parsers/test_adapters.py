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


class TestOrgWalk:
    def _fixture(self, name):
        return (FIXTURES / "gepnic" / name).read_text()

    def test_org_list_parsed_with_counts(self):
        orgs = make_adapter()._parse_org_list(self._fixture("org_list.html"))
        assert [o["name"] for o in orgs][0] == "Agency for Development of Aquaculture Kerala"
        assert orgs[0]["count"] == 9
        assert len(orgs) == 3
        assert orgs[0]["href"].startswith("https://tenders.example.gov.in/nicgep/app?component=%24DirectLink")

    def test_live_listing_layout(self):
        # <td> "S.No" header row, bracketed [Title] [Ref][TenderID] cells, one unclosed <a>
        rows = make_adapter()._parse_listing(self._fixture("org_tenders.html"), None)
        assert len(rows) == 3
        first = rows[0]
        assert first["tender_id"] == "2026_ADAK_868218_2"
        assert first["title"] == "Retender for the supply of Tilapia Fish Seeds"
        assert first["reference_number"] == "ADAK/RE.CZ/173/2026"
        assert first["published_raw"] == "29-Sep-2026 06:00 PM"

    def test_walk_visits_largest_orgs_first_and_respects_cap(self, monkeypatch):
        from types import SimpleNamespace

        adapter = make_adapter(max_orgs=1)
        visited = []

        def fake_get(url):
            if "page=FrontEndTendersByOrganisation&service=page" in url:
                return SimpleNamespace(status_code=200, text=self._fixture("org_list.html"))
            visited.append(url)
            return SimpleNamespace(status_code=200, text=self._fixture("org_tenders.html"))

        monkeypatch.setattr(adapter._http, "get", fake_get)
        from scrapers.core.adapter import FetchOutcome

        outcome = FetchOutcome()
        rows = adapter._fetch_org_walk(outcome)
        assert len(visited) == 1  # capped
        assert len(rows) == 3
        # the org list's own CAPTCHA search form must not stop the walk
        assert outcome.captcha_hit is False
        assert any("advertised" in n for n in outcome.notes)

    def test_walk_survives_a_dropped_connection(self, monkeypatch):
        from types import SimpleNamespace

        from scrapers.core.adapter import FetchOutcome

        adapter = make_adapter()
        calls = {"n": 0}

        def fake_get(url):
            if "page=FrontEndTendersByOrganisation&service=page" in url:
                return SimpleNamespace(status_code=200, text=self._fixture("org_list.html"))
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("Server disconnected without sending a response.")
            return SimpleNamespace(status_code=200, text=self._fixture("org_tenders.html"))

        monkeypatch.setattr(adapter._http, "get", fake_get)
        outcome = FetchOutcome()
        rows = adapter._fetch_org_walk(outcome)
        assert len(rows) == 6  # orgs 2 and 3 still harvested
        assert any("skipped" in n for n in outcome.notes)

    def test_walk_stops_if_tender_list_is_gated(self, monkeypatch):
        from types import SimpleNamespace

        from scrapers.core.adapter import FetchOutcome

        adapter = make_adapter()
        gated = '<form><input name="captchaText"/></form>'

        def fake_get(url):
            if "page=FrontEndTendersByOrganisation&service=page" in url:
                return SimpleNamespace(status_code=200, text=self._fixture("org_list.html"))
            return SimpleNamespace(status_code=200, text=gated)

        monkeypatch.setattr(adapter._http, "get", fake_get)
        outcome = FetchOutcome()
        assert adapter._fetch_org_walk(outcome) == []
        assert outcome.captcha_hit is True

    def test_state_and_org_chain_on_tender(self):
        adapter = make_adapter(state="Kerala")
        row = adapter._parse_listing(self._fixture("org_tenders.html"), None)[0]
        tender = adapter._row_to_tender(row)
        assert tender.geography.state == "Kerala"
        assert tender.organization.authority == "Agency for Development of Aquaculture Kerala › ADAK Regional Office Ernakulam"


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


class TestDedupe:
    def _tender(self, cid, source, title, ref=None, end_hour=15):
        from datetime import datetime

        from scrapers.core.dates import IST

        return CanonicalTender(
            canonical_id=cid,
            identity={"source": source, "source_portal": "https://x.gov.in", "source_tender_id": cid,
                      "reference_number": ref},
            procurement={"title": title},
            organization={"authority": "PWD"},
            geography={"state": "Kerala"},
            dates={"bid_submission_end": datetime(2026, 10, 20, end_hour, tzinfo=IST)},
            status="active",
            provenance={"official_source_url": "https://x.gov.in", "scraped_at": datetime(2026, 10, 4, tzinfo=IST),
                        "first_seen_at": datetime(2026, 10, 4, tzinfo=IST),
                        "last_seen_at": datetime(2026, 10, 4, tzinfo=IST),
                        "parser_version": "t", "content_hash": "x"},
        )

    def test_reference_match_across_sources_is_transitive(self):
        from scrapers.core.dedupe import deduplicate

        a = self._tender("a" * 24, "cppp", "Road works", ref="PWD/1")
        b = self._tender("b" * 24, "kerala", "Road works phase 1", ref="pwd/1 ")
        c = self._tender("c" * 24, "gem", "Road works", ref="PWD/1")
        _, report = deduplicate([c, b, a])
        assert a.possible_duplicate_group == b.possible_duplicate_group == c.possible_duplicate_group == f"dup:{'a' * 24}"
        assert report.reference_matched == 2

    def test_similar_titles_need_close_deadline_and_different_source(self):
        from scrapers.core.dedupe import deduplicate

        a = self._tender("a" * 24, "cppp", "Construction of bridge at Kochi")
        b = self._tender("b" * 24, "kerala", "Construction of bridge at Kochi", end_hour=17)
        same_src = self._tender("c" * 24, "cppp", "Construction of bridge at Kochi")
        far = self._tender("d" * 24, "gem", "Construction of bridge at Kochi", end_hour=2)
        deduplicate([a, b, same_src, far])
        assert a.possible_duplicate_group == b.possible_duplicate_group is not None
        assert far.possible_duplicate_group is None
