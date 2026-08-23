"""Source registry: loads adapter configs from scrapers/configs/*.yaml.

Config keys per source:
  id, family, name, base_url, region, enabled, status, crawl_delay,
  policy_notes, plus family-specific options.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("opentender.registry")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"


@dataclass(frozen=True)
class SourceConfig:
    id: str
    family: str
    name: str
    base_url: str
    region: str
    enabled: bool
    declared_status: str          # from config; runtime health may override
    crawl_delay: float
    policy_notes: str | None
    options: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SourceConfig:
        return cls(
            id=raw["id"],
            family=raw["family"],
            name=raw["name"],
            base_url=raw["base_url"].rstrip("/"),
            region=raw.get("region", "India"),
            enabled=bool(raw.get("enabled", True)),
            declared_status=raw.get("status", "EXPERIMENTAL"),
            crawl_delay=float(raw.get("crawl_delay", 3.0)),
            policy_notes=raw.get("policy_notes"),
            options={k: v for k, v in raw.items() if k not in {
                "id", "family", "name", "base_url", "region", "enabled",
                "status", "crawl_delay", "policy_notes",
            }},
        )


def load_configs(config_dir: Path | None = None) -> list[SourceConfig]:
    directory = config_dir or CONFIG_DIR
    configs: list[SourceConfig] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text("utf-8")) or {}
        except yaml.YAMLError:
            log.exception("bad YAML config %s", path)
            continue
        for entry in raw.get("sources", []):
            try:
                configs.append(SourceConfig.from_dict(entry))
            except KeyError as exc:
                log.error("config %s entry missing key %s", path, exc)
    return configs


def build_adapter(cfg: SourceConfig, *, allow_policy_restricted: bool | None = None):
    """Instantiate the right adapter for a config.

    POLICY_RESTRICTED sources stay disabled unless the operator explicitly
    opts in via OPEN_TENDER_ALLOW_POLICY_RESTRICTED=1 (documented override).
    """
    from scrapers.adapters.gem import GemAdapter
    from scrapers.adapters.gepnic import GePNICAdapter
    from scrapers.adapters.ireps_works import IrepsWorksAdapter

    restricted_ok = (
        os.environ.get("OPEN_TENDER_ALLOW_POLICY_RESTRICTED") == "1"
        if allow_policy_restricted is None
        else allow_policy_restricted
    )
    if cfg.declared_status == "POLICY_RESTRICTED" and not restricted_ok:
        log.info("source %s is POLICY_RESTRICTED and remains disabled", cfg.id)
        return None
    if cfg.family == "gepnic":
        return GePNICAdapter(cfg)
    if cfg.family == "gem":
        return GemAdapter(cfg)
    if cfg.family == "ireps":
        return IrepsWorksAdapter(cfg)
    raise ValueError(f"no adapter for family {cfg.family!r} ({cfg.id})")


def enabled_adapters(config_dir: Path | None = None):
    adapters = []
    for cfg in load_configs(config_dir):
        if not cfg.enabled:
            continue
        adapter = build_adapter(cfg)
        if adapter is not None:
            adapters.append(adapter)
    return adapters
