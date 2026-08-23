"""Canonical tender model (Pydantic v2).

Mirrors packages/schema/canonical_tender.schema.json. A CI test validates
fixtures against both representations to keep them in sync.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"

Status = Literal["active", "closed", "cancelled", "awarded", "retendered", "unknown"]


class TenderIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    source_portal: str
    source_tender_id: str
    tender_number: str | None = None
    reference_number: str | None = None


class ProcurementInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    description: str | None = None
    procurement_type: Literal["goods", "works", "services", "eoi", "auction", "unknown"] | None = None
    tender_type: str | None = None
    contract_type: str | None = None
    category: str | None = None
    subcategory: str | None = None


class OrganizationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ministry: str | None = None
    department: str | None = None
    organization: str | None = None
    division: str | None = None
    authority: str | None = None


class GeographyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str | None = None
    district: str | None = None
    city: str | None = None
    pincode: str | None = None
    location_text: str | None = None


class FinancialInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estimated_value: float | None = Field(default=None, ge=0)
    currency: Literal["INR"] = "INR"
    emd_amount: float | None = Field(default=None, ge=0)
    tender_fee: float | None = Field(default=None, ge=0)
    performance_security_pct: float | None = None


class DateInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published_at: datetime | None = None
    bid_submission_start: datetime | None = None
    bid_submission_end: datetime | None = None
    bid_opening_at: datetime | None = None
    pre_bid_meeting_at: datetime | None = None
    clarification_start: datetime | None = None
    clarification_end: datetime | None = None


class EligibilityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prequalification_text: str | None = None
    experience_requirement_text: str | None = None
    turnover_requirement_text: str | None = None


class WorkInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str | None = None
    period_of_work_days: int | None = Field(default=None, ge=0)
    bid_validity_days: int | None = Field(default=None, ge=0)


class TenderDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    type: str | None = None
    source_url: str
    file_size: int | None = Field(default=None, ge=0)
    hash: str | None = None
    text_extracted: bool = False


class CorrigendumRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_ref: str
    published_at: datetime | None = None
    title: str | None = None
    source_url: str | None = None


class AwardInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    winning_bidder: str | None = None
    award_value: float | None = Field(default=None, ge=0)
    awarded_at: datetime | None = None
    source_url: str | None = None


class ProvenanceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    official_source_url: str
    source_listing_url: str | None = None
    scraped_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    parser_version: str
    content_hash: str


class CanonicalTender(BaseModel):
    """Authoritative record. AI-derived fields never live here."""

    model_config = ConfigDict(extra="forbid")
    schema_version: str = SCHEMA_VERSION
    canonical_id: str
    identity: TenderIdentity
    procurement: ProcurementInfo = ProcurementInfo()
    organization: OrganizationInfo = OrganizationInfo()
    geography: GeographyInfo = GeographyInfo()
    financial: FinancialInfo = FinancialInfo()
    dates: DateInfo = DateInfo()
    eligibility: EligibilityInfo = EligibilityInfo()
    work: WorkInfo = WorkInfo()
    documents: list[TenderDocument] = Field(default_factory=list)
    corrigenda: list[CorrigendumRef] = Field(default_factory=list)
    award: AwardInfo | None = None
    status: Status = "unknown"
    provenance: ProvenanceInfo
    possible_duplicate_group: str | None = None

    @staticmethod
    def make_canonical_id(source: str, source_tender_id: str) -> str:
        digest = hashlib.sha256(f"{source}::{source_tender_id}".encode()).hexdigest()
        return digest[:24]

    def compute_content_hash(self) -> str:
        """Hash of all evidence-bearing fields (excludes timestamps)."""
        payload: dict[str, Any] = self.model_dump(mode="json", exclude={"provenance"})
        blob = repr(sorted(payload.items(), key=lambda kv: kv[0])).encode("utf-8")
        return f"sha256:{hashlib.sha256(blob).hexdigest()}"

    def merge_preserving_history(self, fresh: CanonicalTender) -> tuple[CanonicalTender, bool]:
        """Merge a freshly-scraped record into this one.

        first_seen_at is preserved; last_seen_at/scraped_at updated; fields that
        went missing upstream keep their previous value (never silently blank).
        Returns (merged_tender, changed).
        """
        merged = self.model_copy(deep=True)
        changed = False
        for section in ("procurement", "organization", "geography", "financial", "dates", "eligibility", "work"):
            new_vals = getattr(fresh, section).model_dump(exclude_none=True)
            cur = getattr(merged, section)
            for key, value in new_vals.items():
                if getattr(cur, key) != value:
                    setattr(cur, key, value)
                    changed = True
        if fresh.documents and fresh.documents != merged.documents:
            merged.documents = fresh.documents
            changed = True
        if fresh.corrigenda and fresh.corrigenda != merged.corrigenda:
            merged.corrigenda = fresh.corrigenda
            changed = True
        if fresh.award and fresh.award != merged.award:
            merged.award = fresh.award
            changed = True
        if fresh.status != merged.status:
            merged.status = fresh.status
            changed = True
        now = datetime.now().astimezone()
        merged.provenance.last_seen_at = now
        merged.provenance.scraped_at = fresh.provenance.scraped_at
        merged.provenance.parser_version = fresh.provenance.parser_version
        new_hash = merged.compute_content_hash()
        if new_hash != merged.provenance.content_hash or changed:
            changed = True
        merged.provenance.content_hash = new_hash
        return merged, changed


def canonical_id_for(source: str, source_tender_id: str) -> str:
    return CanonicalTender.make_canonical_id(source, source_tender_id)
