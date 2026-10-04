"""build-index (search docs, retention, quality gate, feeds), store sighting and health fixes."""

from __future__ import annotations

import gzip
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pytest
from typer.testing import CliRunner

import cli
from scrapers.core.dates import IST
from scrapers.core.health import SourceHealthTracker
from scrapers.core.models import CanonicalTender
from scrapers.core.store import TenderStore

ATOM = "{http://www.w3.org/2005/Atom}"
runner = CliRunner()


def _parse(path):
    return ET.parse(path)  # noqa: S314 - our own generated output


def _tender(n: int, *, closing_days: int, title: str | None = None, state: str = "Kerala",
            source: str = "gepnic_kerala", url: str = "https://etenders.example.gov.in/t") -> CanonicalTender:
    now = datetime.now(IST)
    closing = (now + timedelta(days=closing_days)).replace(microsecond=0, second=0, minute=0, hour=12)
    return CanonicalTender(
        canonical_id=f"{n:024x}",
        identity={"source": source, "source_portal": "https://etenders.example.gov.in",
                  "source_tender_id": f"2026_X_{n}_1"},
        procurement={"title": title or f"Road works {n}"},
        organization={"authority": "PWD <Roads>"},
        geography={"state": state},
        dates={"bid_submission_end": closing},
        status="active",
        provenance={"official_source_url": url, "scraped_at": now, "first_seen_at": now,
                    "last_seen_at": now, "parser_version": "t", "content_hash": "x"},
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cli, "STATUS_DIR", tmp_path / "status")
    return tmp_path


def _fill(env, tenders):
    store = TenderStore(env / "data")
    for t in tenders:
        store.upsert(t)
    store.commit_state()


def _docs(env):
    return json.loads(gzip.decompress((env / "data/indexes/search-docs.json.gz").read_bytes()))


def test_build_index_docs_retention_and_feeds(env):
    hostile = 'A & B <script>alert("x")</script> \x07'
    _fill(env, [
        _tender(1, closing_days=5, title=hostile),
        _tender(2, closing_days=-2, state="Goa Daman"),
        _tender(3, closing_days=-90),  # long closed: dropped
    ])
    result = runner.invoke(cli.app, ["build-index"])
    assert result.exit_code == 0, result.output
    docs = _docs(env)
    assert {d["id"] for d in docs} == {f"{1:024x}", f"{2:024x}"}
    d1 = next(d for d in docs if d["id"] == f"{1:024x}")
    assert d1["first_seen_at"] and d1["tender_number"] == "2026_X_1_1"
    assert {"title", "authority", "closing_at", "url"} <= set(d1)
    # heavy fields live in lazily loaded detail shards keyed by the id's first two chars
    assert not {"ai", "documents", "award"} & set(d1)
    shard = json.loads(gzip.decompress((env / f"data/details/{d1['id'][:2]}.json.gz").read_bytes()))
    assert {"ai", "documents", "award", "portal", "opening_at", "last_seen_at"} <= set(shard[d1["id"]])
    assert shard[d1["id"]]["last_seen_at"]

    feeds = env / "data/feeds"
    index = json.loads((feeds / "index.json").read_text())
    paths = {e["path"] for e in index}
    assert {"feeds/all.xml", "feeds/source-gepnic-kerala.xml", "feeds/state-kerala.xml",
            "feeds/state-goa-daman.xml"} <= paths
    for entry in index:
        assert entry["title"] and (env / "data" / entry["path"]).exists()
    root = _parse(feeds / "all.xml").getroot()  # well-formed despite hostile input
    entries = root.findall(f"{ATOM}entry")
    assert len(entries) == 2
    titles = [e.find(f"{ATOM}title").text for e in entries]
    assert 'A & B <script>alert("x")</script> ' in titles  # round-trips as text, not markup
    raw = (feeds / "all.xml").read_text()
    assert "<script>" not in raw
    assert "2026_X_1_1" in raw and "https://etenders.example.gov.in/t" in raw


def test_feed_rejects_non_http_links_and_caps_entries(env):
    _fill(env, [_tender(i, closing_days=5) for i in range(1, 6)] + [_tender(9, closing_days=5, url="javascript:alert(1)")])
    cli._write_feeds(_docs_after_build(env), env / "data/feeds")
    raw = (env / "data/feeds/all.xml").read_text()
    assert "javascript:" not in raw.replace("Official link: javascript:alert(1)", "")
    assert all(e.find(f"{ATOM}link") is None or e.find(f"{ATOM}link").get("href").startswith("http")
               for e in _parse(env / "data/feeds/all.xml").getroot().findall(f"{ATOM}entry"))
    docs = [{"id": f"{i:024x}", "title": "t", "first_seen_at": f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
             "source": "s", "state": None} for i in range(250)]
    cli._write_feeds(docs, env / "data/feeds2")
    assert len(_parse(env / "data/feeds2/all.xml").getroot().findall(f"{ATOM}entry")) == 200


def _docs_after_build(env):
    assert runner.invoke(cli.app, ["build-index"]).exit_code == 0
    return _docs(env)


def test_quality_gate_exit_4_on_empty_and_collapsed(env):
    _fill(env, [_tender(3, closing_days=-90)])  # everything long closed -> empty index
    assert runner.invoke(cli.app, ["build-index"]).exit_code == 4
    assert not (env / "data/indexes/search-docs.json.gz").exists()

    _fill(env, [_tender(i, closing_days=5) for i in range(10, 20)])
    assert runner.invoke(cli.app, ["build-index"]).exit_code == 0
    # collapse: pretend 100 were published before
    meta = env / "data/indexes/search-docs.meta.json"
    meta.write_text(json.dumps({"count": 100}))
    before = (env / "data/indexes/search-docs.json.gz").read_bytes()
    assert runner.invoke(cli.app, ["build-index"]).exit_code == 4
    assert (env / "data/indexes/search-docs.json.gz").read_bytes() == before
    assert runner.invoke(cli.app, ["build-index", "--force"]).exit_code == 0


def test_unchanged_tender_is_not_rewritten_but_last_seen_advances(env):
    store = TenderStore(env / "data")
    store.upsert(_tender(1, closing_days=5))
    path = store._tender_path(f"{1:024x}")
    first_bytes, first_seen = path.read_bytes(), store.last_seen_at(f"{1:024x}")
    store.upsert(_tender(1, closing_days=5))
    assert path.read_bytes() == first_bytes
    # compare instants, not strings: offsets differ between the store and the runner's TZ
    assert datetime.fromisoformat(store.last_seen_at(f"{1:024x}")) >= datetime.fromisoformat(first_seen)
    store.upsert(_tender(1, closing_days=9))  # real change is written
    assert path.read_bytes() != first_bytes


def test_health_zero_after_three_nonzero_is_degraded(tmp_path):
    t = SourceHealthTracker(tmp_path / "s.json")
    for n in (10, 12, 11):
        assert t.record("x", ok=True, discovered=n, new_tenders=0, changed_tenders=0) is False
    assert t.record("x", ok=True, discovered=0, new_tenders=0, changed_tenders=0) is True
    assert t._data["x"]["status"] == "DEGRADED"
    # another zero keeps it degraded; zero never promotes to ACTIVE
    t.record("x", ok=True, discovered=0, new_tenders=0, changed_tenders=0)
    assert t._data["x"]["status"] == "DEGRADED"
    t.record("x", ok=True, discovered=9, new_tenders=0, changed_tenders=0)
    assert t._data["x"]["status"] == "ACTIVE"


def test_health_zero_with_short_history_does_not_activate(tmp_path):
    t = SourceHealthTracker(tmp_path / "s.json")
    t.record("y", ok=True, discovered=0, new_tenders=0, changed_tenders=0)
    assert t._data["y"]["status"] == "EXPERIMENTAL"


def test_status_file_not_rewritten_when_only_timestamps_change(tmp_path):
    path, pub = tmp_path / "status/sources.json", tmp_path / "pub/status-sources.json"
    t = SourceHealthTracker(path, public_file=pub)
    t.record("x", ok=True, discovered=5, new_tenders=1, changed_tenders=0, latency_ms=10)
    assert t.write() is True
    committed = path.read_text()
    t2 = SourceHealthTracker(path, public_file=pub)
    t2.record("x", ok=True, discovered=5, new_tenders=1, changed_tenders=0, latency_ms=999)
    # identical baseline growth would differ, so mimic a stable run by restoring the baseline
    t2._data["x"]["discovered_baseline"] = [5]
    assert t2.write() is False
    assert path.read_text() == committed
    fresh = json.loads(pub.read_text())
    assert set(fresh) == {"generated_at", "sources"} and fresh["sources"]["x"]["status"] == "ACTIVE"
    t2._data["x"]["last_run"]["discovered"] = 6
    t2.record("x", ok=True, discovered=7, new_tenders=0, changed_tenders=0)
    assert t2.write() is True


# --------------------------------------------------------------------------- concurrent fetch


class _FakeAdapter:
    family = "fake"
    active = 0
    peak_per_host: dict[str, int] = {}
    live: dict[str, int] = {}

    def __init__(self, cfg, tenders, boom=False):
        self.cfg, self.tenders, self.boom = cfg, tenders, boom
        self.closed = False

    def fetch_outcome(self):
        import time

        from scrapers.core.adapter import FetchOutcome

        host = self.cfg.base_url
        _FakeAdapter.live[host] = _FakeAdapter.live.get(host, 0) + 1
        _FakeAdapter.peak_per_host[host] = max(_FakeAdapter.peak_per_host.get(host, 0), _FakeAdapter.live[host])
        time.sleep(0.05)
        _FakeAdapter.live[host] -= 1
        if self.boom:
            raise RuntimeError("portal exploded")
        return FetchOutcome(tenders=self.tenders)

    def close(self):
        self.closed = True


def _cfg(sid, base):
    from scrapers.core.registry import SourceConfig

    return SourceConfig(id=sid, family="fake", name=sid, base_url=base, region="IN", enabled=True,
                        declared_status="ACTIVE", crawl_delay=0, policy_notes=None, options={})


def test_concurrent_fetch_isolates_failures_and_serialises_per_host(env, monkeypatch):
    import scrapers.core.registry as registry

    _FakeAdapter.peak_per_host, _FakeAdapter.live = {}, {}
    cfgs = [_cfg(f"s{i}", f"https://host{i}.example.gov.in") for i in range(6)]
    cfgs.append(_cfg("twin_a", "https://shared.example.gov.in"))
    cfgs.append(_cfg("twin_b", "https://shared.example.gov.in"))
    adapters = {}
    for n, c in enumerate(cfgs):
        adapters[c.id] = _FakeAdapter(c, [_tender(100 + n * 10 + k, closing_days=5, source=c.id) for k in range(5)],
                                      boom=(c.id == "s2"))
    monkeypatch.setattr(registry, "load_configs", lambda *a, **k: cfgs)
    monkeypatch.setattr(registry, "build_adapter", lambda cfg, **k: adapters[cfg.id])
    result = runner.invoke(cli.app, ["fetch", "--all", "--workers", "4"])
    assert result.exit_code == 0, result.output
    assert "FATAL: RuntimeError: portal exploded" in result.output
    assert "TOTAL fetched=35 new=35 changed=0" in result.output
    assert len(json.loads((env / "data/state.json").read_text())) == 35
    assert all(a.closed for a in adapters.values())
    assert _FakeAdapter.peak_per_host["https://shared.example.gov.in"] == 1
    snap = json.loads((env / "status/sources.json").read_text())["sources"]
    assert snap["s2"]["status"] != "ACTIVE" and snap["s0"]["status"] == "ACTIVE"


def test_fetch_exit_3_when_nothing_fetched(env, monkeypatch):
    import scrapers.core.registry as registry

    cfg = _cfg("only", "https://only.example.gov.in")
    ad = _FakeAdapter(cfg, [], boom=True)
    monkeypatch.setattr(registry, "load_configs", lambda *a, **k: [cfg])
    monkeypatch.setattr(registry, "build_adapter", lambda c, **k: ad)
    assert runner.invoke(cli.app, ["fetch", "--all"]).exit_code == 3
