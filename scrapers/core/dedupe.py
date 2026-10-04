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


@dataclass
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
    merge time; this pass forms Level-3 possible_duplicate_groups only.

    Only cross-source pairs are considered (Level 1 guarantees uniqueness
    within a source). Candidates are blocked rather than compared all-pairs:
    by normalised reference number, and by closing time - the similarity
    threshold is unreachable without the closing-date signal. Groups are
    transitive (union-find) and named after their smallest member.
    """
    report = DedupeReport()
    by_id = {t.canonical_id: t for t in tenders}
    parent = {cid: cid for cid in by_id}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: CanonicalTender, b: CanonicalTender) -> bool:
        ra, rb = find(a.canonical_id), find(b.canonical_id)
        if ra == rb:
            return False
        parent[max(ra, rb)] = min(ra, rb)
        return True

    by_ref: dict[str, list[CanonicalTender]] = {}
    for t in tenders:
        ref = t.identity.reference_number or t.identity.tender_number
        if ref and ref.strip():
            by_ref.setdefault(ref.strip().upper(), []).append(t)
    for bucket in by_ref.values():
        for a, b in zip(bucket, bucket[1:], strict=False):
            if a.identity.source != b.identity.source and union(a, b):
                report.reference_matched += 1

    # The threshold is unreachable without an identical authority (0.45 + 0.15 +
    # 0.15 < 0.88) and the closing-date signal, so block on (authority, 6h slot);
    # comparing each bucket with the next slot's covers the 6h window. Blocking on
    # time alone put thousands of 6 pm closings from different portals together.
    by_slot: dict[tuple[str, int], list[CanonicalTender]] = {}
    for t in tenders:
        end = t.dates.bid_submission_end
        authority = (t.organization.authority or "").lower()
        if end is not None and authority:
            by_slot.setdefault((authority, int(end.timestamp() // (6 * 3600))), []).append(t)
    for (authority, slot), bucket in by_slot.items():
        neighbours = bucket + by_slot.get((authority, slot + 1), [])
        for i, a in enumerate(bucket):
            for b in neighbours[i + 1 :]:
                if a.identity.source == b.identity.source:
                    continue
                if _similarity(a, b) >= similarity_threshold and union(a, b):
                    report.duplicate_groups_formed += 1

    members: dict[str, int] = {}
    for cid in by_id:
        root = find(cid)
        members[root] = members.get(root, 0) + 1
    for cid, t in by_id.items():
        root = find(cid)
        if members[root] > 1:
            t.possible_duplicate_group = f"dup:{root}"
    return tenders, report
