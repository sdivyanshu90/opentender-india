"""Dataset storage (spec #44).

- Hot data: sharded, gzip-compressed NDJSON under data/hot/<source>/
- Master state: data/state.json mapping canonical_id -> {content_hash, revision,
  changes} used for diffing between runs and powering the timeline.
- Never one giant JSON file; never store source PDFs in git.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from scrapers.core.diff import FieldChange, change_summary, classify_change, diff_tenders
from scrapers.core.models import CanonicalTender

log = logging.getLogger("opentender.store")


class TenderStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.hot_dir = self.root / "hot"
        self.state_file = self.root / "state.json"
        self._state: dict[str, dict] = {}
        if self.state_file.exists():
            self._state = json.loads(self.state_file.read_text("utf-8"))

    # -- state ---------------------------------------------------------------

    def known_hash(self, canonical_id: str) -> str | None:
        rec = self._state.get(canonical_id)
        return rec.get("content_hash") if rec else None

    def existing(self, canonical_id: str) -> CanonicalTender | None:
        path = self._tender_path(canonical_id)
        if not path.exists():
            return None
        try:
            return CanonicalTender.model_validate_json(gzip.decompress(path.read_bytes()))
        except Exception:
            log.exception("unreadable stored tender %s", canonical_id)
            return None

    def upsert(self, tender: CanonicalTender) -> tuple[CanonicalTender | None, list[FieldChange], bool]:
        """Merge into storage. Returns (merged_or_None_if_new, changes, is_new)."""
        cid = tender.canonical_id
        current = self.existing(cid)
        is_new = current is None
        if current is not None:
            merged, changed = current.merge_preserving_history(tender)
            changes = diff_tenders(current, merged) if changed else []
            final = merged
        else:
            final = tender
            changes = []
            final.provenance.first_seen_at = final.provenance.scraped_at
        final.provenance.content_hash = final.compute_content_hash()
        rec = self._state.get(cid, {"revision": 0, "changes": []})
        if changes or is_new:
            rec["revision"] = int(rec.get("revision", 0)) + 1
            serialized = [
                c.as_dict()
                | {"severity": classify_change(c), "summary": change_summary([c])}
                for c in changes
            ]
            rec["changes"] = (rec.get("changes", []) + serialized)[-50:]
        rec["content_hash"] = final.provenance.content_hash
        rec["status"] = final.status
        rec["closing_at"] = final.dates.bid_submission_end.isoformat() if final.dates.bid_submission_end else None
        rec["title"] = final.procurement.title
        rec["source"] = final.identity.source
        rec["value"] = final.financial.estimated_value
        rec["authority"] = final.organization.authority or final.organization.organization
        rec["state"] = final.geography.state
        self._state[cid] = rec
        self._write_tender(final)
        return (None if is_new else final), changes, is_new

    def commit_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self._state, indent=0, sort_keys=True), "utf-8")

    # -- export ---------------------------------------------------------------

    def export_hot_shards(self, out_dir: Path, *, shard_size: int = 500) -> dict[str, object]:
        """Write compressed shards + a manifest for the frontend."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        by_source: dict[str, list[dict]] = defaultdict(list)
        total = 0
        for cid in sorted(self._state):
            path = self._tender_path(cid)
            if not path.exists():
                continue
            record = json.loads(gzip.decompress(path.read_bytes()))
            by_source[record["identity"]["source"]].append(_slim(record))
            total += 1
        shards: list[dict] = []
        for source, records in sorted(by_source.items()):
            src_dir = out_dir / source
            src_dir.mkdir(parents=True, exist_ok=True)
            for i in range(0, len(records), shard_size):
                chunk = records[i : i + shard_size]
                name = f"shard-{i // shard_size:04d}.json.gz"
                blob = gzip.compress(json.dumps(chunk, ensure_ascii=False).encode("utf-8"), mtime=0)
                (src_dir / name).write_bytes(blob)
                shards.append(
                    {
                        "source": source,
                        "file": f"{source}/{name}",
                        "count": len(chunk),
                        "sha256": hashlib.sha256(blob).hexdigest(),
                    }
                )
        manifest = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "total_tenders": total,
            "shards": shards,
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")
        return manifest

    # -- internal ---------------------------------------------------------

    def _tender_path(self, canonical_id: str) -> Path:
        prefix = canonical_id[:2]
        return self.hot_dir / prefix / f"{canonical_id}.json.gz"

    def _write_tender(self, tender: CanonicalTender) -> None:
        path = self._tender_path(tender.canonical_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = gzip.compress(tender.model_dump_json().encode("utf-8"), mtime=0)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        tmp.replace(path)


def _slim(record: dict) -> dict:
    """Frontend payload: drop nothing important but compress key verbosity."""
    return {
        "canonical_id": record["canonical_id"],
        "source": record["identity"]["source"],
        "source_portal": record["identity"]["source_portal"],
        "tender_number": record["identity"].get("tender_number"),
        "reference_number": record["identity"].get("reference_number"),
        "title": record.get("procurement", {}).get("title"),
        "category": record.get("procurement", {}).get("category"),
        "procurement_type": record.get("procurement", {}).get("procurement_type"),
        "authority": record.get("organization", {}).get("authority")
        or record.get("organization", {}).get("organization"),
        "state": record.get("geography", {}).get("state"),
        "city": record.get("geography", {}).get("city"),
        "value": record.get("financial", {}).get("estimated_value"),
        "emd": record.get("financial", {}).get("emd_amount"),
        "fee": record.get("financial", {}).get("tender_fee"),
        "published_at": record.get("dates", {}).get("published_at"),
        "closing_at": record.get("dates", {}).get("bid_submission_end"),
        "opening_at": record.get("dates", {}).get("bid_opening_at"),
        "pre_bid_meeting_at": record.get("dates", {}).get("pre_bid_meeting_at"),
        "status": record.get("status"),
        "official_url": record.get("provenance", {}).get("official_source_url"),
        "first_seen_at": record.get("provenance", {}).get("first_seen_at"),
        "last_seen_at": record.get("provenance", {}).get("last_seen_at"),
        "documents": [
            {"title": d.get("title"), "url": d.get("source_url"), "type": d.get("type")}
            for d in record.get("documents", [])
        ],
        "corrigenda_count": len(record.get("corrigenda", [])),
        "award": record.get("award"),
        "possible_duplicate_group": record.get("possible_duplicate_group"),
    }
