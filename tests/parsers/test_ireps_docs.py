"""Tests for the IREPS works adapter and the secure document pipeline."""

from scrapers.adapters.ireps_works import IrepsWorksAdapter
from scrapers.core.registry import SourceConfig


def make_adapter(**opts) -> IrepsWorksAdapter:
    raw = {
        "id": "ireps_works",
        "family": "ireps",
        "name": "Indian Railways Works",
        "base_url": "https://www.ireps.gov.in",
        "region": "Railways",
        "crawl_delay": 0.0,
        **opts,
    }
    return IrepsWorksAdapter(SourceConfig.from_dict(raw))


ZONE_PAGE = """
<html><body><select name="railwayZone">
<option value="">-- Select --</option>
<option value="401">NORTHERN RLY</option>
<option value="402">NORTH EASTERN RLY</option>
<option value="999">Some Other Option</option>
</select></body></html>
"""

RESULTS_HTML = """
<html><body><table>
<tr><td>Sl.No</td><td>Tender No</td><td>Title</td><td>Closing Date</td></tr>
<tr><td>1</td><td>71255044</td><td>Provision of LED signalling at yard</td><td>15/09/2026 15:30</td></tr>
<tr><td>2</td><td>71256001</td><td>Repairs to foot over bridge</td><td>10/09/2026 11:00</td></tr>
</table></body></html>
"""


class TestIreps:
    def test_zone_parsing(self):
        zones = make_adapter()._parse_zones(ZONE_PAGE)
        ids = [z[0] for z in zones]
        assert "401" in ids and "402" in ids and "999" not in ids

    def test_result_rows(self):
        rows = make_adapter()._parse_results(RESULTS_HTML)
        assert len(rows) == 2
        assert rows[0]["tender_no"] == "71255044"

    def test_row_to_tender_stable_identity(self):
        adapter = make_adapter()
        rows = adapter._parse_results(RESULTS_HTML)
        t1 = adapter._row_to_tender(rows[0], "Northern Rly")
        t2 = adapter._row_to_tender(rows[0], "Northern Rly")
        assert t1.canonical_id == t2.canonical_id
        assert t1.identity.tender_number == "71255044"
        assert "Indian Railways" in t1.organization.authority

    def test_zone_window_capped_at_90(self):
        adapter = make_adapter(window_days=200)
        assert adapter.window_days <= 90  # portal hard limit respected
