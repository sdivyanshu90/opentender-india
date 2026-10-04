"""Source health tracking + zero-result anomaly detection (spec #48, #49)."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

STATUSES = (
    "ACTIVE",
    "EXPERIMENTAL",
    "RESEARCHING",
    "DEGRADED",
    "CAPTCHA_LIMITED",
    "LOGIN_REQUIRED",
    "POLICY_RESTRICTED",
    "RUNNER_BLOCKED",
    "TEMPORARILY_BROKEN",
    "DEPRECATED",
)


def _load_records(raw: dict[str, Any]) -> dict[str, Any]:
    """Accept the current file shape plus the older snapshot-only one."""
    if "records" in raw:
        return raw["records"]
    if "sources" in raw:  # snapshot without records: seed what it carries
        return {
            source: {
                "history": [],
                "discovered_baseline": [],
                "status": snap.get("status", "RESEARCHING"),
                "last_success": snap.get("last_success"),
                "last_attempt": snap.get("last_attempt"),
                "http_failures": snap.get("http_failures_total", 0),
                "parser_failures": snap.get("parser_failures_total", 0),
            }
            for source, snap in raw["sources"].items()
        }
    return raw


_VOLATILE = {
    "generated_at", "last_attempt", "last_success", "at", "latency_ms", "last_latency_ms",
}


def _strip_volatile(obj: Any) -> Any:
    """Drop timestamp/latency keys so only meaningful changes compare unequal."""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in _VOLATILE}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


class SourceHealthTracker:
    """Persists per-run outcomes to status/sources.json history."""

    def __init__(self, status_file: Path, *, baseline_window: int = 30, public_file: Path | None = None):
        self.status_file = Path(status_file)
        self.public_file = Path(public_file) if public_file else None
        self.baseline_window = baseline_window
        self._data: dict[str, Any] = {}
        if self.status_file.exists():
            try:
                self._data = _load_records(json.loads(self.status_file.read_text("utf-8")))
            except Exception:
                self._data = {}

    def record(
        self,
        source: str,
        *,
        ok: bool,
        discovered: int,
        new_tenders: int,
        changed_tenders: int,
        http_errors: int = 0,
        parser_errors: int = 0,
        captcha_hit: bool = False,
        latency_ms: int | None = None,
        parser_version: str | None = None,
    ) -> bool:
        """Record one run. Returns True when the source looks DEGRADED."""
        rec = self._data.setdefault(
            source,
            {
                "history": [],
                "discovered_baseline": deque(maxlen=self.baseline_window),
                "status": "EXPERIMENTAL",
            },
        )
        now = datetime.now().astimezone()
        rec["last_attempt"] = now.isoformat()
        rec["http_failures"] = int(rec.get("http_failures", 0)) + http_errors
        rec["parser_failures"] = int(rec.get("parser_failures", 0)) + parser_errors
        if latency_ms is not None:
            rec["last_latency_ms"] = latency_ms
        if parser_version:
            rec["parser_version"] = parser_version
        # baseline of prior non-zero runs, captured before this run is appended
        prior = [int(x) for x in rec.get("discovered_baseline", [])]
        if ok and discovered > 0:
            rec["last_success"] = now.isoformat()
            rec["consecutive_failures"] = 0
            rec["discovered_baseline"] = list(rec["discovered_baseline"])[-self.baseline_window :] + [discovered]
        else:
            rec["consecutive_failures"] = int(rec.get("consecutive_failures", 0)) + 1
        rec["last_run"] = {
            "at": now.isoformat(),
            "ok": ok,
            "discovered": discovered,
            "new": new_tenders,
            "changed": changed_tenders,
            "captcha_hit": captcha_hit,
        }
        degraded = False
        if ok and discovered == 0 and len(prior) >= 3:
            degraded = True  # HTTP 200 but zero results vs. historical norm
        elif not ok and rec["consecutive_failures"] >= 2:
            degraded = True
        if captcha_hit:
            rec["status"] = "CAPTCHA_LIMITED"
        elif degraded:
            rec["status"] = "DEGRADED"
        elif ok and discovered > 0:
            current = rec.get("status")
            if current in ("DEGRADED", "TEMPORARILY_BROKEN", "CAPTCHA_LIMITED", None, "EXPERIMENTAL"):
                rec["status"] = "ACTIVE"
        elif ok:
            pass  # zero results, no baseline yet: neither promote nor demote
        else:
            rec["status"] = "TEMPORARILY_BROKEN"
        return degraded

    def snapshot(self) -> dict[str, Any]:
        out: dict[str, Any] = {"generated_at": datetime.now().astimezone().isoformat(), "sources": {}}
        for source, rec in sorted(self._data.items()):
            last_run = rec.get("last_run") or {}
            out["sources"][source] = {
                "status": rec.get("status", "RESEARCHING"),
                "last_success": rec.get("last_success"),
                "last_attempt": rec.get("last_attempt"),
                "discovered_last_run": last_run.get("discovered"),
                "new_last_run": last_run.get("new"),
                "changed_last_run": last_run.get("changed"),
                "http_failures_total": rec.get("http_failures", 0),
                "parser_failures_total": rec.get("parser_failures", 0),
                "latency_ms": rec.get("last_latency_ms"),
                "parser_version": rec.get("parser_version"),
            }
        return out

    def write(self) -> bool:
        """Persist state. Returns True when the committed status file was rewritten.

        "sources" is the public view the frontend reads; "records" keeps the
        counters/baselines the next run needs to resume from. The committed file is
        left untouched when only timestamps/latencies changed, so no-op runs create
        no git churn; ``public_file`` (when set) is always written fresh for the site.
        """
        payload = {**self.snapshot(), "records": self._data}
        if self.public_file is not None:
            self.public_file.parent.mkdir(parents=True, exist_ok=True)
            self.public_file.write_text(json.dumps(self.snapshot(), indent=2), "utf-8")
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        new = json.loads(json.dumps(payload, default=list))
        if self.status_file.exists():
            try:
                old = json.loads(self.status_file.read_text("utf-8"))
                if _strip_volatile(old) == _strip_volatile(new):
                    return False
            except Exception:  # noqa: BLE001, S110 - unreadable file: rewrite it
                pass
        self.status_file.write_text(json.dumps(new, indent=2), "utf-8")
        return True

    def stale_sources(self, *, max_age_days: int = 3) -> list[str]:
        cutoff = datetime.now().astimezone() - timedelta(days=max_age_days)
        stale = []
        for source, rec in self._data.items():
            last = rec.get("last_success")
            if not last or datetime.fromisoformat(last) < cutoff:
                stale.append(source)
        return stale
