from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EventClusterMatchResult(BaseModel):
    """Structured response returned upon clustering / deduplication evaluation."""
    article_id: str
    event_id: str | None = None
    match_type: str = "new_event"  # exact_duplicate, near_duplicate, syndicated, semantic_match, new_event
    similarity: float = 0.0
    confidence: float = 0.0
    is_duplicate: bool = False
    is_syndicated: bool = False
    details: dict | None = None


class EventTimelineItem(BaseModel):
    timestamp: str
    article_id: str
    type: str  # initial_report, official_confirmation, update, contradiction
    note: str


class EventResponse(BaseModel):
    id: UUID
    event_id: UUID | None = None
    title: str
    canonical_title: str | None = None
    slug: str
    summary: str | None = None
    description: str | None = None
    category_id: str | None = None
    category: str | None = None
    subcategories: list[str] | None = Field(default_factory=list)
    entities: dict | None = None
    locations: list[str] | None = Field(default_factory=list)
    start_date: datetime | None = None
    start_time: datetime | None = None
    end_date: datetime | None = None
    latest_update: datetime | None = None
    article_count: str = "0"
    source_count: int = 1
    independent_source_count: float = 1.0
    importance_score: float = 0.0
    importance: float = 0.0
    status: str = "active"
    timeline: str | None = None
    timeline_items: list[EventTimelineItem] = []
    article_ids: list[str] = []
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _populate_aliases(cls, value):
        import json
        if hasattr(value, "id"):
            d = {c.name: getattr(value, c.name) for c in value.__table__.columns}
            d["event_id"] = value.id
            d["canonical_title"] = value.title
            d["start_time"] = value.start_date
            d["latest_update"] = value.end_date
            d["importance"] = value.importance_score
            d["article_ids"] = [str(a.id) for a in getattr(value, "__dict__", {}).get("articles", []) if hasattr(a, "id")]
            # Deserialize JSON columns if needed
            if not d.get("subcategories"):
                d["subcategories"] = []
            elif isinstance(d.get("subcategories"), str):
                try:
                    d["subcategories"] = json.loads(d["subcategories"])
                except Exception:
                    d["subcategories"] = []

            if isinstance(d.get("entities"), str):
                try:
                    d["entities"] = json.loads(d["entities"])
                except Exception:
                    d["entities"] = {}

            if not d.get("locations"):
                d["locations"] = []
            elif isinstance(d.get("locations"), str):
                try:
                    d["locations"] = json.loads(d["locations"])
                except Exception:
                    d["locations"] = []

            if isinstance(d.get("timeline"), str):
                try:
                    d["timeline_items"] = json.loads(d["timeline"])
                except Exception:
                    d["timeline_items"] = []
            return d
        if isinstance(value, dict):
            value["event_id"] = value.get("event_id") or value.get("id")
            value["canonical_title"] = value.get("canonical_title") or value.get("title")
            value["start_time"] = value.get("start_time") or value.get("start_date")
            value["latest_update"] = value.get("latest_update") or value.get("end_date")
            value["importance"] = value.get("importance", value.get("importance_score", 0.0))
            return value
        return value


class EventArticleResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    summary: str | None = None
    published_at: str | None = None
    source_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_orm(cls, value):
        if isinstance(value, dict):
            return value
        return {
            "id": value.id,
            "title": value.title,
            "slug": value.slug,
            "summary": value.summary,
            "published_at": value.published_at,
            "source_name": value.source.name if value.source else None,
        }


# ============================================================================
# Summarizer Agent Schemas
# ============================================================================

from enum import Enum


class EventSummaryLength(str, Enum):
    FLASH = "flash"        # 1-2 sentences
    STANDARD = "standard"  # 100-150 words
    DETAILED = "detailed"  # 300-500 words


class SourceReference(BaseModel):
    source_name: str
    publisher_domain: str | None = None
    url: str | None = None
    claims_supported: list[str] = []
    credibility_score: float = 1.0


class UncertaintyItem(BaseModel):
    topic: str
    status: str = "DISPUTED"  # DISPUTED, UNVERIFIED, CONTRADICTED
    explanation: str
    conflicting_claims: list[str] = []


class TimelineEvent(BaseModel):
    timestamp: str
    event: str
    source: str | None = None


class StructuredSummarySections(BaseModel):
    headline: str
    what_happened: str
    key_points: list[str] = []
    timeline: list[str] = []
    why_it_matters: str = ""
    latest_development: str = ""
    conflicting_information: str = ""
    sources: list[str] = []
    confidence: float = 1.0


class EventSummaryOutput(BaseModel):
    """Canonical structured output schema for the Summarizer Agent."""
    event_id: str
    headline: str
    summary: str
    key_points: list[str] = []
    timeline: list[dict] = []
    important_entities: list[dict] = []
    uncertainties: list[dict] = []
    source_references: list[dict] = []
    confidence: float = 0.0
    version: int = 1
    structured_sections: StructuredSummarySections | None = None


class EventSummaryRequest(BaseModel):
    length: EventSummaryLength = EventSummaryLength.STANDARD
    force_regenerate: bool = False
