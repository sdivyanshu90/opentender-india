"""AI task output schemas (spec #37). Every model response is validated here.

Core contract: every claim carries citations into tender evidence, or the
value is NOT_FOUND. Fabricated citations are rejected by validators.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NOT_FOUND = "NOT_FOUND"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_title: str
    page: int | None = Field(default=None, ge=1)
    clause: str | None = None
    quote: str | None = Field(default=None, max_length=400)


class EvidenceField(BaseModel):
    """A single AI-extracted fact bound to its evidence."""

    model_config = ConfigDict(extra="forbid")
    value: str = NOT_FOUND
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    citation: Citation | None = None

    @property
    def is_found(self) -> bool:
        return self.value != NOT_FOUND


class TenderSummary(BaseModel):
    schema_name: ClassVar[str] = "TenderSummary"
    version: ClassVar[str] = "1.0.0"
    opportunity: EvidenceField
    buyer: EvidenceField
    contract_value: EvidenceField
    deadline: EvidenceField
    eligibility: list[EvidenceField] = Field(default_factory=list)
    financial_requirements: list[EvidenceField] = Field(default_factory=list)
    required_experience: list[EvidenceField] = Field(default_factory=list)
    important_documents: list[EvidenceField] = Field(default_factory=list)
    critical_clauses: list[EvidenceField] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("opportunity", "buyer", "deadline", mode="before")
    @classmethod
    def _require_core_fields(cls, v):
        if isinstance(v, dict):
            v.setdefault("value", NOT_FOUND)
        return v


class EligibilityRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement: str
    operator: Literal[">=", "<=", "==", ">", "<", "present"] | None = None
    value: str | None = None
    period: str | None = None
    mandatory: bool = True
    source_page: int | None = None
    source_clause: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class EligibilityExtraction(BaseModel):
    schema_name: ClassVar[str] = "EligibilityExtraction"
    version: ClassVar[str] = "1.0.0"
    requirements: list[EligibilityRequirement]
    exemptions_noted: list[str] = Field(default_factory=list, description="e.g. MSME/Startup EMD exemption")
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("requirements")
    @classmethod
    def _nonempty_requirement(cls, v):
        return [r for r in v if r.requirement.strip()]


class RiskFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Literal["INFO", "REVIEW", "IMPORTANT", "CRITICAL"]
    risk: str
    basis: str  # mandatory explanation - no unexplained flags
    citation: Citation | None = None


class RiskAnalysis(BaseModel):
    schema_name: ClassVar[str] = "RiskAnalysis"
    version: ClassVar[str] = "1.0.0"
    flags: list[RiskFlag]

    @field_validator("flags")
    @classmethod
    def _basis_required(cls, v):
        return [f for f in v if f.basis.strip()]


class CorrigendumChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what_changed: str
    old_value: str | None = None
    new_value: str | None = None
    severity: Literal["INFO", "REVIEW", "IMPORTANT", "CRITICAL"] = "REVIEW"


class CorrigendumSummary(BaseModel):
    schema_name: ClassVar[str] = "CorrigendumSummary"
    version: ClassVar[str] = "1.0.0"
    changes: list[CorrigendumChange]
    deterministic_diff_summary: str  # computed by scrapers.core.diff; AI must not contradict
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


ALL_SCHEMAS = {
    s.schema_name: s for s in (TenderSummary, EligibilityExtraction, RiskAnalysis, CorrigendumSummary)
}

# pipeline task name -> output schema name
TASK_TO_SCHEMA = {
    "tender_summary": "TenderSummary",
    "summary": "TenderSummary",
    "eligibility_extraction": "EligibilityExtraction",
    "risk_analysis": "RiskAnalysis",
    "corrigendum_summary": "CorrigendumSummary",
}


def json_schema_for(name: str) -> dict:
    """JSON Schema used for OpenRouter response_format (draft-07 subset)."""
    model = ALL_SCHEMAS[name]
    return model.model_json_schema()
