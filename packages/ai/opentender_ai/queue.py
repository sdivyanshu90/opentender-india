"""Persistent AI task priority queue (spec #12).

State survives runs (JSONL append + compaction). Priorities:
  1 user_requested          (interactive; reserved budget)
  2 corrigendum_analysis
  3 new_high_value
  4 new_tender
  5 closing_soon
  6 document_extraction
  7 historical_enrichment
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger("opentender.ai.queue")

PRIORITIES = {
    "user_requested": 1,
    "corrigendum_analysis": 2,
    "new_high_value": 3,
    "new_tender": 4,
    "closing_soon": 5,
    "document_extraction": 6,
    "historical_enrichment": 7,
}

HIGH_VALUE_THRESHOLD_INR = 100_000_000.0  # ₹10 Cr, configurable via CLI


@dataclass
class QueueItem:
    task: str                 # summary|eligibility|risk|corrigendum
    canonical_id: str
    priority_name: str
    payload_hash: str         # content hash of the evidence blob
    enqueued_at: str

    @property
    def priority(self) -> int:
        return PRIORITIES.get(self.priority_name, 99)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class AIQueue:
    def __init__(self, state_file: Path):
        self.state_file = Path(state_file)
        self.items: list[QueueItem] = []
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            pending: dict[tuple[str, str], QueueItem] = {}
            done_keys: set[tuple[str, str]] = set()
            for line in self.state_file.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                raw = json.loads(line)
                key = (raw["task"], raw["canonical_id"])
                if raw.get("_done"):
                    done_keys.add(key)
                    continue
                item = QueueItem(
                    task=raw["task"],
                    canonical_id=raw["canonical_id"],
                    priority_name=raw.get("priority_name", "historical_enrichment"),
                    payload_hash=raw.get("payload_hash", ""),
                    enqueued_at=raw.get("enqueued_at", datetime.now().astimezone().isoformat()),
                )
                pending[key] = item  # latest wins
            self.items = [i for k, i in pending.items() if k not in done_keys]
        except Exception:  # noqa: BLE001
            log.exception("AI queue unreadable; starting fresh (state was %s)", self.state_file)

    def enqueue(
        self,
        task: str,
        canonical_id: str,
        *,
        reason: str,
        payload_hash: str = "",
        high_value_threshold: float = HIGH_VALUE_THRESHOLD_INR,
        value: float | None = None,
    ) -> bool:
        """Reason drives priority. Existing pending item for same key is kept."""
        name = {
            "user_requested": "user_requested",
            "corrigendum": "corrigendum_analysis",
            "changed": "corrigendum_analysis",
            "new": "new_high_value" if (value or 0) >= high_value_threshold else "new_tender",
            "closing_soon": "closing_soon",
            "historical": "historical_enrichment",
            "extraction": "document_extraction",
        }.get(reason, "historical_enrichment")
        if any(i.task == task and i.canonical_id == canonical_id for i in self.items):
            return False
        self.items.append(
            QueueItem(
                task=task,
                canonical_id=canonical_id,
                priority_name=name,
                payload_hash=payload_hash,
                enqueued_at=datetime.now().astimezone().isoformat(),
            )
        )
        return True

    def pop_next(self) -> QueueItem | None:
        if not self.items:
            return None
        self.items.sort(key=lambda i: (i.priority, i.enqueued_at))
        return self.items.pop(0)

    def mark_done(self, item: QueueItem) -> None:
        with self.state_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item.as_dict() | {"_done": True}, ensure_ascii=False) + "\n")

    def push_back(self, item: QueueItem) -> None:
        self.items.append(item)

    def persist_pending(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(i.as_dict(), ensure_ascii=False) for i in self.items]
        self.state_file.write_text("\n".join(lines) + ("\n" if lines else ""), "utf-8")

    def status(self) -> dict:
        by_priority: dict[str, int] = {}
        for i in self.items:
            by_priority[i.priority_name] = by_priority.get(i.priority_name, 0) + 1
        return {"pending": len(self.items), "by_priority": by_priority}
