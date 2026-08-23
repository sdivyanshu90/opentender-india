"""Three-level deduplication (spec #43). Never destructively merges."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from scrapers.core.models import CanonicalTender


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    text = title.lower()
    text = re.sub(r"[^a-z0-9\u0900-\u097f ]+", " ", text)  # keep Devanagari
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class DedupeReport:
    exact_merged: int = 0
    reference_matched: int = 0
    duplicate_groups_formed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "exact_source_id": self.exact_merged,
            "reference_number": self.reference_matched,
            "possible_duplicate_groups": self.duplicate_groups_formed,
        }


def _similarity(a: CanonicalTender, b: CanonicalTender) -> float:
    """Level-3 signal: normalized title + authority + geography + closing date."""
    score = 0.0
    ta, tb = normalize_title(a.procurement.title), normalize_title(b.procurement.title)
    if ta and tb:
        score += 0.45 * SequenceMatcher(None, ta, tb).ratio()
    auth_a = (a.organization.authority or "").lower()
    auth_b = (b.organization.authority or "").lower()
    if auth_a and auth_a == auth_b:
        score += 0.25
    state_a = a.geography.state or ""
    state_b = b.geography.state or ""
    if state_a and state_a == state_b:
        score += 0.15
    end_a = a.dates.bid_submission_end
    end_b = b.dates.bid_submission_end
    if end_a and end_b and abs((end_a - end_b).total_seconds()) < 6 * 3600:
        score += 0.15
    return score


def deduplicate(
    tenders: list[CanonicalTender],
    *,
    similarity_threshold: float = 0.88,
) -> tuple[list[CanonicalTender], DedupeReport]:
    """Levels 1+2 are handled upstream by canonical_id / reference matching at
    merge time; this pass forms Level-3 possible_duplicate_groups only."""
    report = DedupeReport()
    groups: dict[str, int] = {}
    n = len(tenders)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = tenders[i], tenders[j]
            if a.identity.source == b.identity.source and not (
                a.identity.tender_number and b.identity.tender_number
                and a.identity.tender_number != b.identity.tender_number
            ):
                continue  # same source: Level-1 already guarantees uniqueness
            ref_a = a.identity.reference_number or a.identity.tender_number
            ref_b = b.identity.reference_number or b.identity.tender_number
            if ref_a and ref_b and ref_a.strip().upper() == ref_b.strip().upper():
                group = groups.get(a.canonical_id) or f"dup:{min(a.canonical_id, b.canonical_id)}"
                groups[a.canonical_id] = hash(group)
                groups[b.canonical_id] = hash(group)
                a.possible_duplicate_group = group
                b.possible_duplicate_group = group
                report.reference_matched += 1
                continue
            if _similarity(a, b) >= similarity_threshold:
                group = f"similar:{min(a.canonical_id, b.canonical_id)}"
                if a.possible_duplicate_group != group:
                    a.possible_duplicate_group = group
                    b.possible_duplicate_group = group
                    report.duplicate_groups_formed += 1
    return tenders, report
