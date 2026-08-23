"""Content-addressed AI cache (spec #11).

Key = SHA256(normalized_input + prompt_version + task_version).
When a tender does not change, its AI artifacts are reused; when content
changes, only affected entries miss the cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("opentender.ai.cache")


def cache_key(*parts: str) -> str:
    normalized = "\x1f".join(p.strip().lower() for p in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class AICache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            self._misses += 1
            return None
        try:
            entry = json.loads(path.read_text("utf-8"))
        except Exception:  # noqa: BLE001 - corrupt entry == miss
            log.warning("corrupt AI cache entry %s", key[:12])
            self._misses += 1
            return None
        entry["cached"] = True
        self._hits += 1
        return entry

    def put(
        self,
        key: str,
        *,
        output: Any,
        model: str,
        prompt_version: str,
        schema_version: str,
        confidence: float | None = None,
    ) -> None:
        entry = {
            "key": key,
            "output": output,
            "model": model,
            "prompt_version": prompt_version,
            "schema_version": schema_version,
            "confidence": confidence,
            "generated_at": datetime.now().astimezone().isoformat(),
        }
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False), "utf-8")
        tmp.replace(path)

    def stats(self) -> dict[str, int | float]:
        return {"entries": sum(1 for _ in self.root.glob("*/*.json")), "hit_rate": round(self.hit_rate, 4)}

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"
