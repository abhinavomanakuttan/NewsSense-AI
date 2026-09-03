"""Pydantic schemas for the Fact-Checking and Verification Agent."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    FACTUAL = "FACTUAL"
    ATTRIBUTION = "ATTRIBUTION"
    NUMERICAL = "NUMERICAL"
    PREDICTION = "PREDICTION"
    OPINION = "OPINION"


class VerificationVerdict(str, Enum):
    WELL_SUPPORTED = "WELL_SUPPORTED"
    DISPUTED = "DISPUTED"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"


class EvidenceItemOutput(BaseModel):
    source_name: str
    url: str | None = None
    passage: str
    publication_date: str | None = None
    source_reliability: float = Field(0.8, ge=0.0, le=1.0)
    retrieval_score: float = Field(0.8, ge=0.0, le=1.0)
    stance: str = "NEUTRAL"  # SUPPORTS, REFUTES, NEUTRAL
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    independence_weight: float = Field(1.0, ge=0.0, le=1.0)


class ClaimVerificationOutput(BaseModel):
    """Canonical graded evidence-based output for a single claim."""
    claim_id: str
    claim: str
    claim_type: str = "FACTUAL"  # FACTUAL, ATTRIBUTION, NUMERICAL, PREDICTION, OPINION
    verdict: str = "UNVERIFIED"  # WELL_SUPPORTED, DISPUTED, UNVERIFIED, CONTRADICTED
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    supporting_evidence: list[EvidenceItemOutput] = Field(default_factory=list)
    refuting_evidence: list[EvidenceItemOutput] = Field(default_factory=list)
    neutral_evidence: list[EvidenceItemOutput] = Field(default_factory=list)
    independent_sources: int = 0
    source_reliability: float = Field(0.5, ge=0.0, le=1.0)


class EventVerificationResponse(BaseModel):
    """Full verification assessment for an event cluster."""
    event_id: str
    overall_trust_score: float = 0.5
    total_claims: int = 0
    supported_claims_count: int = 0
    contradicted_claims_count: int = 0
    disputed_claims_count: int = 0
    unverified_claims_count: int = 0
    claims: list[ClaimVerificationOutput] = Field(default_factory=list)
    critique_alerts: list[str] = Field(default_factory=list)


class VerifyClaimRequest(BaseModel):
    claim: str
    context: str | None = None
    source_url: str | None = None


class VerifyEventRequest(BaseModel):
    force_recheck: bool = False
