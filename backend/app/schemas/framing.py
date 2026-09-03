"""Pydantic schemas for the Bias / Framing Agent in NewsSense AI."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class FramingFeatures(BaseModel):
    """Linguistic and narrative features extracted for a source's coverage."""
    model_config = ConfigDict(from_attributes=True)

    primary_frame: str = Field(description="Dominant narrative frame (e.g. POLICY_AND_TECHNICAL_DETAILS, GOVERNMENT_ACHIEVEMENT, CONTROVERSY_AND_CRITICISM)")
    narrative_emphasis: str = Field(description="Observable narrative focus (e.g. 'Emphasizes economic growth projections')")
    emotional_intensity: float = Field(default=0.0, description="Score 0.0-1.0 measuring density of emotionally charged language")
    sensationalism_score: float = Field(default=0.0, description="Score 0.0-1.0 measuring hyperbolic or clickbait construction")
    active_voice_ratio: float = Field(default=0.8, description="Ratio of active voice vs passive voice construction")
    certainty_level: str = Field(default="high", description="Epistemic certainty (high, moderate, hedged/speculative)")
    quoted_actors: list[str] = Field(default_factory=list, description="Entities, officials, or stakeholders directly quoted")


class SourceComparison(BaseModel):
    """Structured per-source coverage framing comparison."""
    model_config = ConfigDict(from_attributes=True)

    source: str = Field(description="Name of the news publisher or agency")
    headline: str = Field(description="Headline analyzed")
    dominant_topics: list[str] = Field(default_factory=list, description="Primary thematic topics emphasized")
    entities_emphasized: list[str] = Field(default_factory=list, description="Key entities highlighted in headline and lead")
    tone: str = Field(description="Dominant tone (e.g. objective_analytical, critical_skeptical, congratulatory, alarmist)")
    sentiment: str = Field(description="Overall sentiment polarity (neutral, positive, negative, mixed)")
    key_facts: list[str] = Field(default_factory=list, description="Verified facts or data points actively reported")
    omitted_or_less_emphasized_facts: list[str] = Field(default_factory=list, description="Facts reported by peers but omitted or downplayed")
    framing_features: FramingFeatures = Field(description="Extracted discourse and linguistic features")


class EventFramingResponse(BaseModel):
    """Complete multi-source event framing analysis response matching user specification."""
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    sources: list[str] = Field(default_factory=list, description="List of publisher names compared")
    comparisons: list[SourceComparison] = Field(default_factory=list, description="Per-source framing breakdowns")
    framing_patterns: list[str] = Field(default_factory=list, description="Observed macro framing contrasts across publishers")
    language_patterns: list[str] = Field(default_factory=list, description="Observed linguistic differences (emotional tone, voice, certainty)")
    areas_of_agreement: list[str] = Field(default_factory=list, description="Factual core unanimously reported by all sources")
    areas_of_difference: list[str] = Field(default_factory=list, description="Observable differences in emphasis, narrative angle, or omissions")
    confidence: float = Field(default=0.85, description="Confidence score in the comparative framing analysis (0.0 to 1.0)")


class AnalyzeEventRequest(BaseModel):
    """Request payload to trigger event framing analysis."""
    force_recheck: bool = Field(default=False, description="Whether to bypass cached framing analysis")


class ArticleInput(BaseModel):
    """Input article for standalone framing comparison."""
    source_name: str
    headline: str
    lead_paragraph: str = ""
    content: str = ""


class CompareArticlesRequest(BaseModel):
    """Request payload to compare framing across arbitrary article texts."""
    event_title: str
    articles: list[ArticleInput]
