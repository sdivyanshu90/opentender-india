"""AI request budget manager (spec #10).

Free inference is scarce. The manager persists counters per UTC day and
refuses (rather than overruns) when the ceiling is reached, reserving
headroom by default so interactive tasks never starve.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("opentender.ai.budget")


@dataclass
class BudgetCounters:
    day: str = ""
    requests: int = 0
    tokens_sent: int = 0
    tokens_received: int = 0
    failures: int = 0
    retries: int = 0
    cache_hits: int = 0
    estimated_cost_usd: float = 0.0
    per_task: dict[str, int] = field(default_factory=dict)
    latency_ms_total: int = 0


class AIBudgetManager:
    def __init__(
        self,
        state_file: Path,
        *,
        max_requests_per_day: int = 40,
        reserve_ratio: float = 0.2,
    ):
        self.state_file = Path(state_file)
        self.max_requests_per_day = max_requests_per_day
        self.reserve = int(max_requests_per_day * reserve_ratio)
        self.counters = BudgetCounters()
        self._load()

    # -- public ---------------------------------------------------------------

    @property
    def today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def can_spend(self, *, task_type: str = "general", reserved: bool = False) -> bool:
        self._roll_day()
        if self.counters.requests >= self.max_requests_per_day:
            return False
        if not reserved and self.counters.requests >= self.max_requests_per_day - self.reserve:
            log.info("budget headroom exhausted for non-reserved task %s", task_type)
            return False
        return True

    def record_request(self, *, task_type: str) -> None:
        self._roll_day()
        self.counters.requests += 1
        self.counters.per_task[task_type] = self.counters.per_task.get(task_type, 0) + 1

    def record_usage(
        self,
        *,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        cost: float | None,
        latency_ms: int,
        failed: bool = False,
    ) -> None:
        if failed:
            self.counters.failures += 1
        else:
            self.counters.tokens_sent += prompt_tokens or 0
            self.counters.tokens_received += completion_tokens or 0
            self.counters.latency_ms_total += latency_ms
        if cost:
            self.counters.estimated_cost_usd += float(cost)

    def record_cache_hit(self) -> None:
        self.counters.cache_hits += 1

    @property
    def cache_hit_rate(self) -> float:
        total = self.counters.requests + self.counters.cache_hits
        return self.counters.cache_hits / total if total else 0.0

    def snapshot(self) -> dict:
        return {
            "max_requests_per_day": self.max_requests_per_day,
            "reserved_headroom": self.reserve,
            **asdict(self.counters),
            "avg_latency_ms": (
                self.counters.latency_ms_total / max(1, self.counters.requests)
            ),
        }

    def persist(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.snapshot(), indent=2), "utf-8")

    # -- internal -----------------------------------------------------------

    def _roll_day(self) -> None:
        if self.counters.day != self.today:
            self.counters = BudgetCounters(day=self.today)

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            raw = json.loads(self.state_file.read_text("utf-8"))
            for key in ("requests", "tokens_sent", "tokens_received", "failures",
                        "retries", "cache_hits"):
                setattr(self.counters, key, int(raw.get(key, 0)))
            self.counters.day = raw.get("day", "")
            self.counters.per_task = raw.get("per_task", {})
            self._roll_day()
        except Exception:  # noqa: BLE001
            log.exception("unreadable AI budget state; starting fresh")
