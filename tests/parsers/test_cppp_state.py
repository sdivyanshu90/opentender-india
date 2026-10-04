"""CPPP state-tenders adapter: parsing, pagination, CAPTCHA guard, budgeting (no network)."""

from __future__ import annotations

import base64
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from scrapers.adapters.cppp_state import (
    CpppStateAdapter,
    day_url,
    normalise_state,
    page_url,
    parse_rows,
    parse_total,
    plan_pages,
)
from scrapers.core.http import detect_captcha
from scrapers.core.registry import SourceConfig, build_adapter, load_configs

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "cppp_state"
BASE = "https://eprocure.gov.in"


def fx(name: str) -> str:
    return (FIX / name).read_text("utf-8")


def make_adapter(http=None, **opts) -> CpppStateAdapter:
    cfg = SourceConfig.from_dict(
        {"id": "cppp_state", "family": "cppp_state", "name": "CPPP state", "base_url": BASE,
         "crawl_delay": 0, **opts}
    )
    return CpppStateAdapter(cfg, http=http or SimpleNamespace(get=None, close=lambda: None))


class TestParsing:
    def test_total_and_rows(self):
        html = fx("day_page0.html")
        assert parse_total(html) == 5545
        rows = parse_rows(html)
        assert len(rows) == 4
        r = rows[0]
        assert r["title"] == "Bearings for use ata Pump section"
        assert r["reference_number"] == "ER226O0138"
        assert r["tender_id"] == "735179"
        assert r["state_raw"] == "Telangana"

    def test_gepnic_ids_and_ref_with_spaces(self):
        r = parse_rows(fx("day_gepnic_ids.html"))[0]
        assert r["tender_id"] == "2026_PWD_144962_1"
        assert r["reference_number"] == "NIT No. 6739-6790 dated 09.10.2026"
        assert r["title"].endswith("Km 0/0 to 1/650")  # slashes inside the title survive
        assert r["state_raw"] == "Himachal Pradesh"

    def test_gepnic_id_is_the_source_key(self):
        a = make_adapter()
        row = parse_rows(fx("day_gepnic_ids.html"))[0]
        t = a._row_to_tender(row, day_url(BASE, date(2026, 10, 11)))
        assert t.identity.source_tender_id == "2026_PWD_144962_1"
        assert t.geography.state == "Himachal Pradesh"
        assert t.dates.bid_submission_end.isoformat().startswith("2026-10-11T11:00")
        assert t.provenance.official_source_url.endswith("/byday/by2026-10-11")
        assert "tendersfullviewmmp" not in (t.provenance.source_listing_url or "")

    def test_numeric_id_is_state_scoped(self):
        a = make_adapter()
        t = a._row_to_tender(parse_rows(fx("day_page0.html"))[0], "u")
        assert t.identity.source_tender_id == "telangana:735179"

    def test_central_psu_rows_keep_org_not_state(self):
        a = make_adapter()
        t = a._row_to_tender(parse_rows(fx("central_psu_rows.html"))[0], "u")
        assert t.geography.state is None
        assert t.organization.authority == "Bharat Petroleum Corporation Limited"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Keralam", "Kerala"), ("Kerala", "Kerala"), ("NCT of Delhi", "Delhi"),
            ("Ladakh UT", "Ladakh"), ("Jammu and Kashmir", "Jammu and Kashmir"),
            ("Orissa", "Odisha"), ("Maharashtra", "Maharashtra"), ("Tamil Nadu", "Tamil Nadu"),
            ("Andaman and Nicobar Island", "Andaman and Nicobar Islands"), ("Ministry of Railways", None), ("", None), (None, None),
        ],
    )
    def test_normalise_state(self, raw, expected):
        assert normalise_state(raw) == expected


class TestPagination:
    def test_page_url_decodes_to_page_param(self):
        base = day_url(BASE, date(2026, 10, 6))
        assert base.endswith("/cppp/statetendersclosingbydays/byday/by2026-10-06")
        url = page_url(base, 2)
        token = parse_qs(urlparse(url).query)["url"][0]
        assert base64.b64decode(token).decode() == f"{base}?page=2"
        # matches the link CPPP itself emits for page 2
        assert url.endswith("?url=aHR0cHM6Ly9lcHJvY3VyZS5nb3YuaW4vY3BwcC9zdGF0ZXRlbmRlcnNjbG9zaW5nYnlkYXlzL2J5ZGF5L2J5MjAyNi0xMC0wNj9wYWdlPTI%3D")

    def test_plan_full_budget_reads_everything(self):
        plan = plan_pages({date(2026, 10, 6): 35, date(2026, 10, 7): 5}, 100)
        assert plan[date(2026, 10, 6)] == [1, 2, 3]
        assert plan[date(2026, 10, 7)] == []

    def test_plan_is_proportional_and_bounded(self):
        totals = {date(2026, 10, 6): 1001, date(2026, 10, 7): 101}
        plan = plan_pages(totals, 11)
        assert sum(len(v) for v in plan.values()) <= 11
        assert len(plan[date(2026, 10, 6)]) > len(plan[date(2026, 10, 7)])
        assert all(1 <= p <= 100 for p in plan[date(2026, 10, 6)])
        assert plan_pages(totals, 0) == {d: [] for d in totals}


class TestCaptcha:
    def test_cppp_wording(self):
        assert detect_captcha(fx("captcha_gate.html"))
        assert detect_captcha("<label>What code is in the image?</label>")

    def test_existing_behaviour_unchanged(self):
        assert detect_captcha('<input name="captchaText"/>')
        assert detect_captcha("Please Provide Captcha")
        assert not detect_captcha(fx("day_page0.html"))


class FakeHttp:
    def __init__(self, pages: dict | None = None, fail_all=False, status=200, html=None):
        self.calls: list[str] = []
        self.fail_all, self.status, self.html = fail_all, status, html

    def get(self, url):
        self.calls.append(url)
        if self.fail_all:
            raise ConnectionError("dropped")
        return SimpleNamespace(status_code=self.status, text=self.html or fx("day_page0.html"))

    def close(self):
        pass


class TestRun:
    def test_budget_is_respected_and_coverage_logged(self):
        http = FakeHttp()
        a = make_adapter(http, days_ahead=3, max_pages_per_run=10)
        out = a.fetch_outcome(today=date(2026, 10, 4))
        assert len(http.calls) <= 10
        assert http.calls[0].endswith("/byday/by2026-10-05")
        assert any("coverage" in n and "pages" in n for n in out.notes)
        assert out.tenders  # the same fixture rows repeat, deduped by key
        assert len(out.tenders) == 4

    def test_states_include_filters(self):
        a = make_adapter(FakeHttp(html=fx("central_psu_rows.html")), days_ahead=1, max_pages_per_run=1,
                         states_include=["Maharashtra"])
        assert a.fetch_outcome(today=date(2026, 10, 4)).tenders == []

    def test_captcha_stops_politely(self):
        http = FakeHttp(html=fx("captcha_gate.html"))
        out = make_adapter(http, days_ahead=5, max_pages_per_run=50).fetch_outcome(today=date(2026, 10, 4))
        assert out.captcha_hit and len(http.calls) == 1

    def test_three_consecutive_failures_stop(self):
        http = FakeHttp(fail_all=True)
        out = make_adapter(http, days_ahead=10, max_pages_per_run=50).fetch_outcome(today=date(2026, 10, 4))
        assert len(http.calls) == 3
        assert any("3 consecutive" in n for n in out.notes)

    def test_http_error_stops(self):
        http = FakeHttp(status=503)
        make_adapter(http, days_ahead=5).fetch_outcome(today=date(2026, 10, 4))
        assert len(http.calls) == 1


class TestRegistry:
    def test_builds_adapter(self):
        cfg = next(c for c in load_configs() if c.id == "cppp_state")
        assert cfg.family == "cppp_state" and cfg.declared_status == "EXPERIMENTAL"
        assert cfg.crawl_delay == 4.5
        adapter = build_adapter(cfg)
        assert isinstance(adapter, CpppStateAdapter)
        assert adapter.max_pages == 1500 and adapter.days_ahead == 45
        adapter.close()
