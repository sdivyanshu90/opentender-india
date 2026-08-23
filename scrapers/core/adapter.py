"""TenderSourceAdapter contract (spec #76).

Every source implements discover/fetch_* + normalize + healthcheck and fails
independently of every other source.
"""

from __future__ import annotations

import abc
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime

from scrapers.core.http import HttpClient
from scrapers.core.models import CanonicalTender


@dataclass(frozen=True)
class AdapterMeta:
    source_code: str                 # e.g. "gepnic_kerala"
    source_name: str                 # human name
    portal_family: str               # gepnic | gem | ireps | custom
    base_url: str
    region: str                      # state/UT/central/psu name
    crawl_delay: float = 3.0
    max_concurrency: int = 1         # we are strictly polite: 1 by default
    supports_documents: bool = False
    supports_results: bool = False
    supports_corrigenda: bool = True
    supports_incremental: bool = True
    policy_notes: str | None = None  # robots/CAPTCHA caveats shown publicly


@dataclass
class FetchOutcome:
    tenders: list[CanonicalTender] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    captcha_hit: bool = False
    degraded: bool = False           # HTTP ok but looks wrong (zero-result anomaly)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.captcha_hit and not self.degraded


class TenderSourceAdapter(abc.ABC):
    """Base class. Subclasses must be deterministic given the same responses."""

    meta: AdapterMeta

    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient(min_delay=self.meta.crawl_delay)

    # -- lifecycle ----------------------------------------------------------

    @abc.abstractmethod
    def fetch_incremental(self, *, since: datetime | None = None) -> Iterator[CanonicalTender]:
        """Yield new/updated tenders for a daily run."""

    def fetch_detail(self, tender: CanonicalTender) -> CanonicalTender:
        """Optional second pass; default returns input unchanged."""
        return tender

    def healthcheck(self) -> dict[str, object]:
        started = datetime.now()
        try:
            ok = self._healthcheck_impl()
            error = None if ok else "portal responded but expected markers missing"
        except Exception as exc:  # noqa: BLE001 - health must never raise
            ok, error = False, f"{type(exc).__name__}: {exc}"
        return {
            "source": self.meta.source_code,
            "ok": ok,
            "error": error,
            "checked_at": started.astimezone().isoformat(),
            "latency_ms": int((datetime.now() - started).total_seconds() * 1000),
        }

    def _healthcheck_impl(self) -> bool:
        raise NotImplementedError

    # -- helpers -------------------------------------------------------------

    def close(self) -> None:
        self.http.close()
