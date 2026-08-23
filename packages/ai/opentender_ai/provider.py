"""OpenRouter provider (spec #8, verified against docs 2026-08).

- POST /api/v1/chat/completions (OpenAI-compatible)
- model fallback via `models[]`; Retry-After honored on 429/503
- structured outputs via response_format json_schema when supported
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

log = logging.getLogger("opentender.ai.provider")

BASE_URL = "https://openrouter.ai/api/v1"
APP_REFERER = "https://github.com/opentender-india/opentender-india"
APP_TITLE = "OpenTender India"


class AIUnavailableError(RuntimeError):
    """Raised when no AI path is available - callers must degrade gracefully."""


class AIProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema_name: str | None = None,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
        timeout_s: float = 90.0,
    ) -> dict[str, Any]:
        """Returns {"content": str, "model": str, "usage": {...}}."""
        ...


@dataclass
class OpenRouterProvider:
    api_key: str | None = field(default=None, repr=False)
    models: list[str] = field(default_factory=list)
    name: str = "openrouter"
    _client: httpx.Client | None = None

    MAX_ATTEMPTS = 2
    RETRYABLE_STATUS = {429, 502, 503}

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.models:
            self.models = [m for m in os.environ.get("OPENROUTER_MODEL", "openrouter/free").split(",") if m]
        if not self.api_key:
            raise AIUnavailableError("OPENROUTER_API_KEY not configured; AI disabled")

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=BASE_URL,
                timeout=httpx.Timeout(120.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": APP_REFERER,
                    "X-Title": APP_TITLE,
                },
            )
        return self._client

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema_name: str | None = None,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
        timeout_s: float = 90.0,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "models": self.models,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_schema and schema_name:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": json_schema},
            }
        last_error = ""
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                resp = self.client.post("/chat/completions", json=body)
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                continue
            except httpx.HTTPError as exc:
                last_error = f"http error: {exc}"
                break
            if resp.status_code == 200:
                return self._parse_ok(resp)
            retry_after = resp.headers.get("Retry-After")
            if resp.status_code in self.RETRYABLE_STATUS and attempt < self.MAX_ATTEMPTS:
                wait = float(retry_after) if retry_after and retry_after.replace(".", "").isdigit() else 5.0 * attempt
                log.warning("AI %s; retrying in %.0fs", resp.status_code, wait)
                time.sleep(min(wait, 60))
                continue
            try:
                err_body = resp.json()
                last_error = str(err_body.get("error", {}).get("message", resp.text[:200]))
            except Exception:  # noqa: BLE001
                last_error = f"HTTP {resp.status_code}"
            break
        raise AIUnavailableError(f"OpenRouter request failed: {last_error}")

    def _parse_ok(self, resp: httpx.Response) -> dict[str, Any]:
        try:
            body = resp.json()
        except json.JSONDecodeError as exc:
            raise AIUnavailableError(f"malformed JSON envelope: {exc}") from exc
        choices = body.get("choices") or []
        if not choices:
            raise AIUnavailableError("empty choices")
        content = (choices[0].get("message") or {}).get("content")
        if content is None:
            raise AIUnavailableError("missing message content")
        usage = body.get("usage") or {}
        return {
            "content": content,
            "model": body.get("model") or "unknown",
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "cost": usage.get("cost"),
            },
        }

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


def available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))
