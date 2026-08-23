"""Polite HTTP client for official portals.

Rules enforced here:
- descriptive User-Agent (never spoof browsers);
- per-host minimum delay + jitter;
- robots.txt awareness helpers;
- no proxy/anti-bot evasion of any kind.
"""

from __future__ import annotations

import logging
import random
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

log = logging.getLogger("opentender.http")

USER_AGENT = (
    "OpenTenderIndiaBot/0.1 (+https://github.com/opentender-india/opentender-india; "
    "open-source tender intelligence; contact: repository issues)"
)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=15.0)


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: bytes
    elapsed_ms: int
    from_cache: bool = False

    @property
    def text(self) -> str:
        return self.content.decode(self._encoding(), errors="replace")

    def _encoding(self) -> str:
        return "utf-8"


class PolitenessPolicy:
    """Per-host pacing state."""

    def __init__(self, default_min_delay: float = 3.0, jitter: float = 1.5):
        self.default_min_delay = default_min_delay
        self.jitter = jitter
        self._last_hit: dict[str, float] = {}

    def wait(self, host: str, min_delay: float | None = None) -> None:
        delay = min_delay if min_delay is not None else self.default_min_delay
        now = time.monotonic()
        last = self._last_hit.get(host)
        if last is not None:
            remaining = delay + random.uniform(0, self.jitter) - (now - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_hit[host] = time.monotonic()


@dataclass
class HttpClient:
    """Session-scoped client with cookie jar and politeness."""

    min_delay: float = 3.0
    jitter: float = 1.5
    respect_robots: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)
    _client: httpx.Client | None = None
    _policy: PolitenessPolicy | None = None
    _robots: dict[str, urllib.robotparser.RobotFileParser] | None = None

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, **self.extra_headers},
        )
        self._policy = PolitenessPolicy(self.min_delay, self.jitter)
        self._robots = {}

    # -- public API ---------------------------------------------------------

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> FetchResult:
        return self.request("GET", url, headers=headers)

    def post(
        self,
        url: str,
        *,
        data: dict[str, str] | bytes | None = None,
        json: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        return self.request("POST", url, data=data, json=json, headers=headers)

    def request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | bytes | None = None,
        json: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        host = urlparse(url).netloc
        self._policy.wait(host)
        allowed = self.url_allowed(url)
        if not allowed:
            raise RobotsDisallowedError(url)
        started = time.monotonic()
        resp = self._client.request(method, url, data=data, json=json, headers=headers)
        elapsed = int((time.monotonic() - started) * 1000)
        log.debug("fetch %s %s -> %s (%dms)", method, url, resp.status_code, elapsed)
        return FetchResult(url=str(resp.url), status_code=resp.status_code, content=resp.content, elapsed_ms=elapsed)

    def url_allowed(self, url: str) -> bool:
        """Consult robots.txt when enabled. Network failures on robots.txt are
        treated conservatively (allow) so that a broken robots endpoint does
        not take down ingestion; portal outages surface elsewhere."""
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
            except Exception:
                log.warning("robots.txt unreadable for %s; allowing with caution", base)
                self._robots[base] = rp
                return True
            self._robots[base] = rp
        return rp.can_fetch(USER_AGENT, url) or rp.can_fetch("*", url)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


class RobotsDisallowedError(RuntimeError):
    pass


def detect_captcha(html: str) -> bool:
    """Runtime guard used by GePNIC-family adapters: never proceed past a CAPTCHA."""
    lowered = html.lower()
    return 'name="captchatext"' in lowered or "provide captcha" in lowered
