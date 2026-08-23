"""Deterministic revision diffing (spec #42, #23). No AI involved here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scrapers.core.models import CanonicalTender


@dataclass(frozen=True)
class FieldChange:
    field: str
    old: Any
    new: Any
    detected_at: str

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "old": self.old, "new": self.new, "detected_at": self.detected_at}


# Sections/fields whose changes matter most for corrigendum intelligence.
_TRACKED = {
    "procurement": ("title", "description", "category"),
    "organization": ("authority",),
    "financial": ("estimated_value", "emd_amount", "tender_fee"),
    "dates": (
        "published_at",
        "bid_submission_start",
        "bid_submission_end",
        "bid_opening_at",
        "pre_bid_meeting_at",
        "clarification_end",
    ),
    "eligibility": ("prequalification_text", "experience_requirement_text", "turnover_requirement_text"),
    "work": ("scope", "period_of_work_days", "bid_validity_days"),
}

_DEADLINE_FIELDS = {"dates.bid_submission_end", "dates.bid_opening_at"}
_VALUE_FIELDS = {"financial.estimated_value", "financial.emd_amount", "financial.tender_fee"}


def diff_tenders(old: CanonicalTender, new: CanonicalTender) -> list[FieldChange]:
    now = datetime.now().astimezone().isoformat()
    changes: list[FieldChange] = []
    for section, keys in _TRACKED.items():
        old_sec = getattr(old, section)
        new_sec = getattr(new, section)
        for key in keys:
            old_v = getattr(old_sec, key)
            new_v = getattr(new_sec, key)
            if old_v != new_v:
                if old_v is None and new_v is None:
                    continue
                changes.append(
                    FieldChange(
                        field=f"{section}.{key}",
                        old=_ser(old_v),
                        new=_ser(new_v),
                        detected_at=now,
                    )
                )
    if old.status != new.status:
        changes.append(FieldChange("status", old.status, new.status, now))
    if len(new.corrigenda) > len(old.corrigenda):
        changes.append(
            FieldChange(
                "corrigenda.count",
                len(old.corrigenda),
                len(new.corrigenda),
                now,
            )
        )
    return changes


def classify_change(change: FieldChange) -> str:
    """Deterministic severity used by the frontend timeline + digest."""
    if change.field in _DEADLINE_FIELDS:
        return "CRITICAL"
    if change.field in _VALUE_FIELDS or change.field.startswith("eligibility."):
        return "IMPORTANT"
    if change.field.startswith("status"):
        return "IMPORTANT"
    return "REVIEW"


def change_summary(changes: list[FieldChange]) -> str:
    """Deterministic one-line summary (AI may later rephrase, never invent)."""
    parts: list[str] = []
    for c in changes:
        label = c.field.split(".")[-1].replace("_", " ")
        if c.field == "corrigenda.count":
            parts.append(f"corrigendum added ({c.new} total)")
        elif c.old is None:
            parts.append(f"{label} set to {c.new}")
        else:
            parts.append(f"{label}: {c.old} → {c.new}")
    return "; ".join(parts) if parts else "no tracked changes"


def _ser(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
