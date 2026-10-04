"""`opentender` CLI (spec #84).

Commands
  sources        list configured sources + statuses
  health         run portal healthchecks
  fetch          discover/crawl sources (--all | source id)
  validate       validate stored dataset against canonical schema
  dedupe         run Level-3 similarity pass over stored data
  ai queue|run|status   manage budgeted AI enrichment
  build-index    generate frontend datasets + evidence chunks
  digest         deterministic daily briefing (markdown)
  stats          dataset statistics
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import typer

logging.basicConfig(
    level=os.environ.get("OPEN_TENDER_LOG", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

ROOT = Path(os.environ.get("OPEN_TENDER_ROOT", Path(__file__).resolve().parent))
DATA_DIR = ROOT / "data"
STATUS_DIR = ROOT / "status"

app = typer.Typer(help="OpenTender India - open tender intelligence pipeline", no_args_is_help=True)
ai_app = typer.Typer(help="AI enrichment commands")
app.add_typer(ai_app, name="ai")


def _store():
    from scrapers.core.store import TenderStore

    return TenderStore(DATA_DIR)


def _health_tracker():
    from scrapers.core.health import SourceHealthTracker

    # status/sources.json is committed (only rewritten on real changes); the public copy
    # for the site is always fresh and travels via the site-data artifact.
    return SourceHealthTracker(STATUS_DIR / "sources.json", public_file=DATA_DIR / "public" / "status-sources.json")


# --------------------------------------------------------------------------- sources


@app.command()
def sources() -> None:
    """List every configured source and its declared status."""
    from scrapers.core.registry import load_configs

    cfgs = load_configs()
    if not cfgs:
        typer.echo("No sources configured.")
        raise typer.Exit(1)
    widths = (26, 10, 12, 46)
    typer.echo(f"{'SOURCE':<{widths[0]}} {'FAMILY':<{widths[1]}} {'STATUS':<{widths[2]}} NAME")
    for c in cfgs:
        enabled = "" if c.enabled else " [disabled]"
        typer.echo(
            f"{c.id:<{widths[0]}} {c.family:<{widths[1]}} {c.declared_status:<{widths[2]}} "
            f"{c.name}{enabled}"
        )


@app.command()
def health(source: str | None = typer.Argument(None)) -> None:
    """Run portal healthchecks (smoke tests)."""
    from scrapers.core.registry import build_adapter, load_configs

    tracker = _health_tracker()
    failures = 0
    for cfg in load_configs():
        if source and cfg.id != source:
            continue
        adapter = build_adapter(cfg)
        if adapter is None:
            typer.secho(f"{cfg.id}: POLICY_RESTRICTED (skipped)", fg=typer.colors.YELLOW)
            continue
        result = adapter.healthcheck()
        adapter.close()
        color = typer.colors.GREEN if result["ok"] else typer.colors.RED
        if not result["ok"]:
            failures += 1
        rec = tracker._data.setdefault(cfg.id, {"history": [], "discovered_baseline": [], "status": cfg.declared_status})
        rec["last_healthcheck"] = result
        typer.secho(
            f"{cfg.id}: {'OK' if result['ok'] else 'FAIL'} ({result['latency_ms']}ms)"
            + (f" - {result['error']}" if result.get("error") else ""),
            fg=color,
        )
    tracker.write()
    raise typer.Exit(1 if failures else 0)


# --------------------------------------------------------------------------- fetch


def _fetch_group(group, results) -> None:
    """Worker thread: fetch one host's sources strictly one after another (politeness).

    Only network/parsing happens here; every store/tracker/console side effect is done by
    the main thread. Never raises - failures are handed back as the result.
    """
    for cfg, adapter in group:
        started = datetime.now()
        outcome = error = None
        try:
            outcome = adapter.fetch_outcome()
        except Exception as exc:  # noqa: BLE001 - failure isolation per source
            error = exc
        finally:
            try:
                adapter.close()
            except Exception:  # noqa: BLE001
                logging.getLogger("opentender.fetch").exception("closing adapter %s", cfg.id)
        results.put((cfg, adapter, outcome, error, int((datetime.now() - started).total_seconds() * 1000)))


@app.command()
def fetch(
    source: str | None = typer.Argument(None, help="source id, or omit with --all"),
    all_sources: bool = typer.Option(False, "--all"),
    limit: int = typer.Option(None, help="max tenders per source (testing)"),
    workers: int = typer.Option(8, min=1, help="sources fetched concurrently (one host is never fetched concurrently)"),
) -> None:
    """Fetch new/updated tenders. Each source fails independently."""
    import queue
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import urlparse

    from scrapers.core.registry import build_adapter, load_configs

    if not source and not all_sources:
        typer.echo("Pass a source id or --all")
        raise typer.Exit(2)
    store = _store()
    tracker = _health_tracker()
    totals = {"fetched": 0, "new": 0, "changed": 0}
    summary: dict[str, str] = {}
    order: list[str] = []
    groups: dict[str, list] = {}
    for cfg in load_configs():
        if source and cfg.id != source:
            continue
        adapter = build_adapter(cfg)
        if adapter is None:
            typer.secho(f"{cfg.id}: skipped (POLICY_RESTRICTED)", fg=typer.colors.YELLOW)
            continue
        order.append(cfg.id)
        groups.setdefault(urlparse(cfg.base_url).netloc or cfg.id, []).append((cfg, adapter))
    results: queue.Queue = queue.Queue()
    pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(groups) or 1)), thread_name_prefix="fetch")
    for group in groups.values():
        pool.submit(_fetch_group, group, results)
    for _ in range(len(order)):
        cfg, adapter, outcome, error, latency_ms = results.get()
        typer.echo(f"[{cfg.id}] fetched")
        discovered = new = changed = 0
        ok = True
        captcha_hit = False
        try:
            if error is not None:
                raise error
            if limit:
                outcome.tenders = outcome.tenders[:limit]
            discovered = len(outcome.tenders)
            for tender in outcome.tenders:
                merged, changes, is_new = store.upsert(tender)
                if is_new:
                    new += 1
                elif changes:
                    changed += 1
            for err in outcome.errors:
                typer.secho(f"  error: {err}", fg=typer.colors.RED)
            ok = not outcome.errors and not outcome.degraded
            for note in outcome.notes:
                typer.echo(f"  note: {note}")
            captcha_hit = outcome.captcha_hit
            if outcome.captcha_hit:
                typer.secho("  CAPTCHA encountered - stopped politely", fg=typer.colors.YELLOW)
        except Exception as exc:  # noqa: BLE001 - failure isolation per source
            ok = False
            typer.secho(f"  FATAL: {type(exc).__name__}: {exc}", fg=typer.colors.RED)
        degraded = tracker.record(
            cfg.id,
            ok=ok,
            discovered=discovered,
            new_tenders=new,
            changed_tenders=changed,
            parser_errors=0 if ok else 1,
            captcha_hit=captcha_hit and discovered == 0,
            latency_ms=latency_ms,
            parser_version=f"{adapter.family}-1.0.0",
        )
        if degraded:
            typer.secho("  ⚠ anomaly detected → DEGRADED", fg=typer.colors.YELLOW)
        typer.echo(f"[{cfg.id}] discovered={discovered} new={new} changed={changed}")
        summary[cfg.id] = f"| {cfg.id} | {'✅' if ok else '⚠️'} | {discovered} | {new} | {changed} |"
        totals["fetched"] += discovered
        totals["new"] += new
        totals["changed"] += changed
        store.commit_state()
    pool.shutdown(wait=True)
    tracker.write()
    typer.echo(f"TOTAL fetched={totals['fetched']} new={totals['new']} changed={totals['changed']}")
    _job_summary(
        ["## Ingestion", "", "| source | ok | discovered | new | changed |", "|---|---|---|---|---|",
         *(summary[c] for c in order),
         "", f"**Total:** {totals['fetched']} fetched, {totals['new']} new, {totals['changed']} changed"]
    )
    exit_code = 0
    if summary and totals["fetched"] == 0:
        # every source failing at once is an outage or a parser break, never a quiet success
        typer.secho("no tenders fetched from any source", fg=typer.colors.RED)
        exit_code = 3
    raise typer.Exit(exit_code)


def _job_summary(lines: list[str]) -> None:
    """Append Markdown to the GitHub Actions job summary when running in CI."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- quality


@app.command()
def validate() -> None:
    """Validate every stored tender against the canonical JSON schema."""
    import jsonschema

    schema = json.loads((ROOT / "packages/schema/canonical_tender.schema.json").read_text("utf-8"))
    # compile once: jsonschema.validate() re-checks the schema on every call,
    # which made this step take most of an hour at ~60k tenders
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    store = _store()
    bad = total = 0
    for cid in list(store._state):
        path = store._tender_path(cid)
        if not path.exists():
            continue
        record = json.loads(gzip.decompress(path.read_bytes()))
        total += 1
        error = jsonschema.exceptions.best_match(validator.iter_errors(record))
        if error is not None:
            bad += 1
            typer.secho(f"INVALID {cid}: {error.message[:140]}", fg=typer.colors.RED)
    typer.echo(f"validated {total} tenders, {bad} invalid")
    raise typer.Exit(1 if bad else 0)


@app.command()
def dedupe() -> None:
    """Level-3 cross-source duplicate grouping over stored data."""
    from scrapers.core.dedupe import deduplicate

    store = _store()
    tenders = []
    for cid in list(store._state):
        t = store.existing(cid)
        if t is not None:
            tenders.append(t)
    _, report = deduplicate(tenders)
    for t in tenders:
        if t.possible_duplicate_group:
            store.upsert(t)
    store.commit_state()
    typer.echo(json.dumps(report.as_dict(), indent=1))


@app.command()
def parse(file: Path = typer.Argument(..., exists=True)) -> None:  # noqa: B008
    """Parse a downloaded document (PDF/XLSX) to extracted text preview."""
    from scrapers.core.parsers.documents import extract_text

    result = extract_text(file)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=1)[:4000])


@app.command()
def stats() -> None:
    """Dataset statistics."""
    store = _store()
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    values = []
    closing_soon = 0
    now = datetime.now().astimezone()
    for cid in list(store._state):
        t = store.existing(cid)
        if t is None:
            continue
        by_source[t.identity.source] = by_source.get(t.identity.source, 0) + 1
        by_status[t.status] = by_status.get(t.status, 0) + 1
        if t.financial.estimated_value:
            values.append(t.financial.estimated_value)
        if (
            t.dates.bid_submission_end
            and t.status == "active"
            and 0 <= (t.dates.bid_submission_end - now).days <= 7
        ):
            closing_soon += 1
    payload = {
        "generated_at": now.isoformat(),
        "total": sum(by_source.values()) or 0,
        "by_source": by_source,
        "by_status": by_status,
        "closing_within_7_days": closing_soon,
        "value_known": len(values),
        "value_total_inr": sum(values) if values else 0,
    }
    typer.echo(json.dumps(payload, indent=1))


# --------------------------------------------------------------------------- AI


@ai_app.command("queue")
def ai_queue(
    reason: str = typer.Option("historical", help="new|changed|closing_soon|historical"),
    limit: int = typer.Option(50),
    task: str = typer.Option("tender_summary"),
) -> None:
    """Enqueue pending tenders for AI enrichment."""
    from opentender_ai.queue import AIQueue

    store = _store()
    queue = AIQueue(DATA_DIR / "ai-queue.jsonl")
    added = 0
    for cid in list(store._state):
        if added >= limit:
            break
        rec = store._state[cid]
        value = rec.get("value")
        is_recent = bool(rec.get("last_seen_at"))
        if reason == "closing_soon":
            closing = rec.get("closing_at")
            if not closing:
                continue
        if queue.enqueue(task, cid, reason=reason, payload_hash=rec.get("content_hash", ""), value=value):
            added += 1
        del is_recent
    queue.persist_pending()
    typer.echo(f"enqueued {added}; {json.dumps(queue.status())}")


@ai_app.command("run")
def ai_run(max_tasks: int = typer.Option(20), reserve_for_interactive: bool = typer.Option(True)) -> None:
    """Process the AI queue within today's request budget."""
    from opentender_ai.budget import AIBudgetManager
    from opentender_ai.cache import AICache
    from opentender_ai.provider import OpenRouterProvider, available
    from opentender_ai.queue import AIQueue
    from opentender_ai.tasks import AITaskRunner

    if not available():
        typer.secho("OPENROUTER_API_KEY not set - AI disabled; pipeline continues without it.", fg=typer.colors.YELLOW)
        raise typer.Exit(0)
    max_per_day = int(os.environ.get("MAX_AI_REQUESTS_PER_DAY", "40"))
    budget = AIBudgetManager(STATUS_DIR / "ai-budget.json", max_requests_per_day=max_per_day)
    cache = AICache(DATA_DIR / "ai-cache")
    provider = OpenRouterProvider()
    runner = AITaskRunner(provider=provider, cache=cache, budget=budget)
    queue = AIQueue(DATA_DIR / "ai-queue.jsonl")
    store = _store()
    done = failed = 0
    processed_ids: set[str] = set()
    while done + failed < max_tasks:
        item = queue.pop_next()
        if item is None:
            break
        tender = store.existing(item.canonical_id)
        if tender is None:
            queue.mark_done(item)
            continue
        meta = {
            "title": tender.procurement.title,
            "authority": tender.organization.authority,
            "state": tender.geography.state,
            "value_inr": tender.financial.estimated_value,
            "emd_inr": tender.financial.emd_amount,
            "tender_fee": tender.financial.tender_fee,
            "closing_at": str(tender.dates.bid_submission_end),
            "category": tender.procurement.category,
            "source": tender.identity.source,
            "official_url": tender.provenance.official_source_url,
        }
        chunks = _evidence_chunks(tender.canonical_id)
        result = runner.run_task(
            item.task,
            tender_meta=meta,
            chunks=chunks,
            payload_fingerprint=tender.provenance.content_hash,
            reserved=(item.priority_name == "user_requested"),
        )
        if result.ok:
            out_path = DATA_DIR / "hot" / ".ai" / f"{item.canonical_id}.{item.task}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(result.output, ensure_ascii=False), "utf-8")
            queue.mark_done(item)
            done += 1
            typer.echo(f"ok {item.task} {item.canonical_id} ({result.model}, cache={'hit' if result.from_cache else 'miss'})")
        else:
            failed += 1
            typer.secho(f"fail {item.task} {item.canonical_id}: {result.error}", fg=typer.colors.RED)
            if result.error and "budget" in result.error.lower():
                queue.push_back(item)
                break
            # malformed output twice: drop after recording
            queue.mark_done(item)
        processed_ids.add(item.canonical_id)
    queue.persist_pending()
    budget.persist()
    typer.echo(f"AI run complete: done={done} failed={failed}; budget={json.dumps(budget.snapshot())}")


@ai_app.command("status")
def ai_status() -> None:
    from opentender_ai.queue import AIQueue

    queue = AIQueue(DATA_DIR / "ai-queue.jsonl")
    budget_file = STATUS_DIR / "ai-budget.json"
    budget = json.loads(budget_file.read_text("utf-8")) if budget_file.exists() else {}
    typer.echo(json.dumps({"queue": queue.status(), "budget": budget}, indent=1))


def _evidence_chunks(canonical_id: str):
    from opentender_ai.tasks import EvidenceChunk

    chunks_file = DATA_DIR / "indexes" / "chunks" / f"{canonical_id}.json.gz"
    out = []
    if chunks_file.exists():
        raw = json.loads(gzip.decompress(chunks_file.read_bytes()))
        for ch in raw[:12]:
            out.append(EvidenceChunk(document_title=ch["doc"], page=ch.get("page"), text=ch["text"]))
    return out


# --------------------------------------------------------------------------- index & feeds


@app.command("build-index")
def build_index(
    retention_days: int = typer.Option(30, help="Drop tenders that closed more than N days ago from the frontend index."),
    max_drop: float = typer.Option(0.5, help="Refuse to publish if the index shrinks by more than this fraction."),
    force: bool = typer.Option(False, help="Publish even when the quality gate fails."),
) -> None:
    """Generate frontend datasets + evidence chunk indexes + feeds."""
    store = _store()
    manifest = store.export_hot_shards(DATA_DIR / "index")
    count, previous = _write_search_docs(store, retention_days=retention_days, max_drop=max_drop, force=force)
    _job_summary(["## Index", "", f"{count} tenders published (previous: {previous if previous is not None else 'n/a'})"])
    n_chunks = _build_chunk_indexes(store)
    _write_digest(store)
    typer.echo(f"index built: {manifest['total_tenders']} tenders, {n_chunks} evidence chunks")


def _write_search_docs(store, *, retention_days: int, max_drop: float, force: bool) -> tuple[int, int | None]:
    from scrapers.core.geo import infer_geography

    out_dir = DATA_DIR / "indexes"
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "search-docs.meta.json"
    previous = None
    if meta_path.exists():
        try:
            previous = int(json.loads(meta_path.read_text("utf-8"))["count"])
        except (ValueError, KeyError, TypeError):
            previous = None
    now = datetime.now().astimezone()
    horizon = now.timestamp() - retention_days * 86400
    docs = []
    for cid in sorted(store._state):
        rec = store.existing(cid)
        if rec is None:
            continue
        closing = rec.dates.bid_submission_end
        if closing is not None and closing.timestamp() < horizon:
            continue  # long closed: kept in the store/archive, not shipped to browsers
        status = rec.status
        if status == "active" and closing is not None and closing < now:
            status = "closed"  # sources only re-list open tenders, so derive it here
        ai_summary = _load_ai_artifact(cid, "tender_summary")
        eligibility = _load_ai_artifact(cid, "eligibility_extraction") or _load_ai_artifact(cid, "summary")
        risk = _load_ai_artifact(cid, "risk_analysis")
        doc = {
            "id": cid,
            "title": rec.procurement.title,
            "authority": rec.organization.authority,
            "state": rec.geography.state,
            "city": rec.geography.city,
            "category": rec.procurement.category,
            "type": rec.procurement.procurement_type,
            "value": rec.financial.estimated_value,
            "emd": rec.financial.emd_amount,
            "fee": rec.financial.tender_fee,
            "published_at": rec.dates.published_at.isoformat(timespec="minutes") if rec.dates.published_at else None,
            "closing_at": rec.dates.bid_submission_end.isoformat(timespec="minutes") if rec.dates.bid_submission_end else None,
            "pre_bid_meeting_at": rec.dates.pre_bid_meeting_at.isoformat(timespec="minutes") if rec.dates.pre_bid_meeting_at else None,
            "opening_at": rec.dates.bid_opening_at.isoformat(timespec="minutes") if rec.dates.bid_opening_at else None,
            "status": status,
            "source": rec.identity.source,
            "portal": rec.identity.source_portal,
            "ref": rec.identity.reference_number,
            # GePNIC keys records by their public Tender ID (e.g. 2026_LSGD_875715_6); expose it so
            # users can search for it. Provisional keys ("hash:", "bid:") are internal only.
            "tender_number": rec.identity.tender_number
            or (None if rec.identity.source_tender_id.startswith(("hash:", "bid:")) else rec.identity.source_tender_id),
            "url": rec.provenance.official_source_url,
            "first_seen_at": rec.provenance.first_seen_at.isoformat(timespec="minutes"),
            "last_seen_at": store.last_seen_at(cid) or rec.provenance.last_seen_at.isoformat(),
            "documents": [d.model_dump(mode="json") for d in rec.documents],
            "corrigenda_count": len(rec.corrigenda),
            "award": rec.award.model_dump(mode="json") if rec.award else None,
            "ai": {
                "summary": ai_summary,
                "eligibility": eligibility,
                "risk": risk,
            },
        }
        if not rec.geography.state:
            # central/PSU/GeM sources carry no state: infer it deterministically (never overrides an adapter)
            tag = infer_geography(rec)
            if tag is not None:
                doc["state"] = tag.state
                doc["state_inferred"] = True
                if tag.district and not rec.geography.district:
                    doc["district"] = tag.district
        docs.append(doc)
    # quality gate (spec 8/46): never overwrite a good dataset with an empty or collapsed one
    collapsed = previous is not None and previous > 0 and len(docs) < previous * (1 - max_drop)
    if not force and (not docs or collapsed):
        typer.secho(
            f"quality gate failed: {len(docs)} tenders (previous {previous}); keeping the published index",
            fg=typer.colors.RED,
        )
        raise typer.Exit(4)
    _write_detail_shards(docs, DATA_DIR / "details")
    slim = [{k: v for k, v in d.items() if k not in DETAIL_FIELDS} for d in docs]
    blob = gzip.compress(json.dumps(slim, ensure_ascii=False).encode("utf-8"), mtime=0)
    (out_dir / "search-docs.json.gz").write_bytes(blob)
    (out_dir / "search-docs.meta.json").write_text(
        json.dumps({"count": len(docs), "sha256": hashlib.sha256(blob).hexdigest()}, indent=1),
        "utf-8",
    )
    _write_feeds(docs, DATA_DIR / "feeds")
    return len(docs), previous


# Fields only the tender page needs. They ship in 256 small shards keyed by the
# first two hex chars of the id, so the list every visitor downloads stays slim
# at ~60k tenders (spec 37: no gigantic homepage dataset).
DETAIL_FIELDS = ("documents", "ai", "award", "portal", "fee", "pre_bid_meeting_at", "city", "opening_at", "last_seen_at")


def _write_detail_shards(docs: list[dict], out_dir: Path) -> None:
    import shutil

    shutil.rmtree(out_dir, ignore_errors=True)  # ids that left the index must not linger
    out_dir.mkdir(parents=True, exist_ok=True)
    shards: dict[str, dict[str, dict]] = {}
    for d in docs:
        shards.setdefault(d["id"][:2].lower(), {})[d["id"]] = {k: d.get(k) for k in DETAIL_FIELDS}
    for key, payload in shards.items():
        blob = gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"), mtime=0)
        (out_dir / f"{key}.json.gz").write_bytes(blob)


# --------------------------------------------------------------------------- atom feeds (spec #22)

FEED_LIMIT = 200
_ATOM_NS = "http://www.w3.org/2005/Atom"
_XML_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _xml_text(value) -> str:
    """Strip characters XML 1.0 cannot carry; escaping itself is done by ElementTree."""
    return _XML_BAD.sub("", str(value))


def _atom_feed(title: str, feed_id: str, docs: list[dict]) -> bytes:
    import xml.etree.ElementTree as ET

    ET.register_namespace("", _ATOM_NS)
    feed = ET.Element(f"{{{_ATOM_NS}}}feed")

    def add(parent, tag, text=None, **attrs):
        el = ET.SubElement(parent, f"{{{_ATOM_NS}}}{tag}", {k: _xml_text(v) for k, v in attrs.items()})
        if text is not None:
            el.text = _xml_text(text)
        return el

    add(feed, "title", title)
    add(feed, "id", f"urn:opentender-india:feed:{feed_id}")
    add(feed, "updated", max((d["first_seen_at"] for d in docs), default="1970-01-01T00:00:00+00:00"))
    for d in docs:
        entry = add(feed, "entry")
        add(entry, "title", d.get("title") or "Untitled tender")
        add(entry, "id", f"urn:opentender-india:tender:{d['id']}")
        add(entry, "updated", d.get("last_seen_at") or d["first_seen_at"])
        add(entry, "published", d["first_seen_at"])
        url = d.get("url") or ""
        if url.startswith(("http://", "https://")):  # never emit javascript:/data: links from scraped text
            add(entry, "link", rel="alternate", href=url)
        add(entry, "author").append(_name_el(d.get("authority") or d.get("portal") or "Unknown authority"))
        parts = [
            f"Authority: {d.get('authority') or 'n/a'}",
            f"Closing: {d.get('closing_at') or 'n/a'}",
            f"Tender number: {d.get('tender_number') or 'n/a'}",
            f"Official link: {url or 'n/a'}",
        ]
        add(entry, "summary", "\n".join(parts), type="text")
    ET.indent(feed)
    return ET.tostring(feed, encoding="utf-8", xml_declaration=True)


def _name_el(text: str):
    import xml.etree.ElementTree as ET

    el = ET.Element(f"{{{_ATOM_NS}}}name")
    el.text = _xml_text(text)
    return el


def _write_feeds(docs: list[dict], out_dir: Path) -> None:
    """data/feeds/all.xml, source-<id>.xml, state-<slug>.xml and index.json (newest first)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in list(out_dir.glob("*.xml")) + list(out_dir.glob("index.json")):
        old.unlink()  # feeds for sources/states that vanished must not linger
    newest = sorted(docs, key=lambda d: (d["first_seen_at"], d["id"]), reverse=True)
    groups: list[tuple[str, str, list[dict]]] = [("OpenTender India - all tenders", "all", newest)]
    by_source: dict[str, list[dict]] = {}
    by_state: dict[str, list[dict]] = {}
    for d in newest:
        if d.get("source"):
            by_source.setdefault(d["source"], []).append(d)
        if d.get("state"):
            by_state.setdefault(d["state"], []).append(d)
    for src in sorted(by_source):
        groups.append((f"OpenTender India - source {src}", f"source-{_slug(src)}", by_source[src]))
    seen: set[str] = set()
    for state in sorted(by_state):
        slug = _slug(state)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        groups.append((f"OpenTender India - {state}", f"state-{slug}", by_state[state]))
    index = []
    for title, name, items in groups:
        (out_dir / f"{name}.xml").write_bytes(_atom_feed(title, name, items[:FEED_LIMIT]))
        index.append({"title": title, "path": f"feeds/{name}.xml"})
    (out_dir / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), "utf-8")


def _load_ai_artifact(cid: str, task: str):
    p = DATA_DIR / "hot" / ".ai" / f"{cid}.{task}.json"
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def _build_chunk_indexes(store) -> int:
    """Deterministic page-preserving chunks of extracted document text (spec #25)."""
    from scrapers.core.parsers.documents import chunk_extracted_text

    out_dir = DATA_DIR / "indexes" / "chunks"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    text_dir = DATA_DIR / "extracted-text"
    if not text_dir.exists():
        return 0
    for cid in sorted(store._state):
        tfile = text_dir / f"{cid}.json.gz"
        if not tfile.exists():
            continue
        try:
            pages = json.loads(gzip.decompress(tfile.read_bytes()))
        except Exception:  # noqa: BLE001, S112
            continue
        chunks = chunk_extracted_text(pages)
        if chunks:
            blob = gzip.compress(json.dumps(chunks, ensure_ascii=False).encode("utf-8"), mtime=0)
            (out_dir / f"{cid}.json.gz").write_bytes(blob)
            count += len(chunks)
    return count


def _write_digest(store) -> None:
    """Deterministic daily digest (spec #32): verified numbers only, no AI."""
    now = datetime.now().astimezone()
    lines = [
        "# OpenTender India — Daily Digest",
        "",
        f"_Generated {now.strftime('%d %b %Y %H:%M IST')} from verified portal data._",
        "",
    ]
    sections = [
        ("New Today", lambda r: r["rec"].provenance.first_seen_at.date() == now.date()),
        ("Closing Soon (7 days)", lambda r: r["rec"].status == "active" and r["rec"].dates.bid_submission_end is not None and 0 <= (r["rec"].dates.bid_submission_end - now).days <= 7),
    ]
    all_records = [(store.existing(cid), ) for cid in sorted(store._state)]
    all_records = [{"rec": pair[0]} for pair in all_records if pair[0] is not None]
    for title, pred in sections:
        items = [r for r in all_records if pred(r)]
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        for r in sorted(items, key=lambda x: x["rec"].financial.estimated_value or 0, reverse=True)[:15]:
            rec = r["rec"]
            value = f"₹{rec.financial.estimated_value / 1e7:.2f} Cr" if rec.financial.estimated_value else "value not disclosed"
            close = rec.dates.bid_submission_end.strftime("%d %b %H:%M") if rec.dates.bid_submission_end else "—"
            lines.append(f"- [{rec.procurement.title or 'Untitled'}]({rec.provenance.official_source_url}) — {rec.organization.authority or ''} — {value} — closes {close}")
        if not items:
            lines.append("- none")
        lines.append("")
    feeds_dir = STATUS_DIR / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    target = feeds_dir / "daily-digest.md"
    text = "\n".join(lines)
    if target.exists():
        # the "_Generated ..._" stamp alone must not turn a no-op run into a commit
        strip = lambda t: "\n".join(x for x in t.splitlines() if not x.startswith("_Generated "))  # noqa: E731
        if strip(target.read_text("utf-8")) == strip(text):
            return
    target.write_text(text, "utf-8")


@app.command()
def version() -> None:
    from scrapers import __version__

    typer.echo(f"opentender-india {__version__}")


@app.command()
def archive(
    older_than_days: int = typer.Option(180, help="Archive closed tenders not seen in N days."),
    compact: bool = typer.Option(True, help="Write gzip partitions by source/year/month."),
) -> None:
    """Move stale closed tenders from hot storage into compressed archives."""
    import gzip as _gzip
    from collections import defaultdict

    store = _store()
    now = datetime.now().astimezone()
    cutoff = now.timestamp() - older_than_days * 86400
    archived: dict[str, list[dict]] = defaultdict(list)
    removed = 0
    for cid in list(store._state):
        rec = store._state[cid]
        last_seen = rec.get("closing_at") or ""
        try:
            ts = datetime.fromisoformat(last_seen).timestamp() if last_seen else 0
        except ValueError:
            continue
        # stored status can stay "active" after a tender leaves the listings, so go by the deadline
        if not ts or ts > cutoff:
            continue
        tender = store.existing(cid)
        if tender is None:
            continue
        key = f"{tender.identity.source}/{ts and datetime.fromtimestamp(ts, tz=now.tzinfo).strftime('%Y/%m')}"
        archived[key].append(json.loads(tender.model_dump_json()))
        path = store._tender_path(cid)
        if path.exists():
            path.unlink()
        del store._state[cid]
        removed += 1
    if compact and archived:
        for key, records in sorted(archived.items()):
            out = ROOT / "archive" / f"{key.replace('/', '_')}.json.gz"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():  # partitions accumulate across runs; never overwrite earlier records
                merged = {r["canonical_id"]: r for r in json.loads(_gzip.decompress(out.read_bytes()))}
                merged.update({r["canonical_id"]: r for r in records})
                records = list(merged.values())
            blob = _gzip.compress(json.dumps(records, ensure_ascii=False).encode(), mtime=0)
            out.write_bytes(blob)
    store.commit_state()
    typer.echo(f"archived {removed} tenders into {len(archived)} partition(s)")


def app_main() -> None:
    app()


if __name__ == "__main__":
    app_main()
