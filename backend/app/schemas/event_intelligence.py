"""Comprehensive Event Intelligence Schema combining synthesis, fact checks, framing, and timeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.event import EventSummaryOutput
from app.schemas.framing import EventFramingResponse
from app.schemas.verification import ClaimVerificationOutput


class TimelineEntry(BaseModel):
    """Chronological event update point."""
    time: str = Field(description="Display time (e.g. '09:00' or ISO timestamp)")
    title: str = Field(description="Development description")
    source: str = Field(default="NewsWire", description="Attributed publisher")
    note: str | None = None


class EventClaimsBreakdown(BaseModel):
    """Categorized fact-checked claims for the event."""
    well_supported: list[ClaimVerificationOutput] = Field(default_factory=list)
    disputed: list[ClaimVerificationOutput] = Field(default_factory=list)
    unverified: list[ClaimVerificationOutput] = Field(default_factory=list)
    contradicted: list[ClaimVerificationOutput] = Field(default_factory=list)


class EventIntelligenceResponse(BaseModel):
    """Unified intelligence response for the event detail view."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    category: str | None = None
    importance_score: float = 0.8
    status: str = "active"
    start_date: str | None = None
    end_date: str | None = None
    article_count: int = 1
    sources: list[str] = Field(default_factory=list)
    summary: EventSummaryOutput
    timeline: list[TimelineEntry] = Field(default_factory=list)
    claims: EventClaimsBreakdown = Field(default_factory=EventClaimsBreakdown)
    framing: EventFramingResponse | None = None
    latest_updates: list[str] = Field(default_factory=list)
    related_events: list[dict[str, Any]] = Field(default_factory=list)
