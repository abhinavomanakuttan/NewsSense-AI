"""SQLAlchemy ORM Model for Event Framing & Bias Analysis."""

from __future__ import annotations

import json
from sqlalchemy import Column, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class EventFramingAnalysis(Base, TimestampMixin, UUIDMixin):
    """Stores multi-source coverage framing, discourse, and omission analysis for an event."""

    __tablename__ = "event_framing_analyses"

    event_id = Column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)

    sources_analyzed = Column(Text, nullable=False, default="[]")  # JSON list of source names
    comparisons = Column(Text, nullable=False, default="[]")  # JSON list of SourceComparison dicts
    framing_patterns = Column(Text, nullable=False, default="[]")  # JSON list of narrative patterns
    language_patterns = Column(Text, nullable=False, default="[]")  # JSON list of linguistic observations
    areas_of_agreement = Column(Text, nullable=False, default="[]")  # JSON list of consensus facts
    areas_of_difference = Column(Text, nullable=False, default="[]")  # JSON list of divergent angles
    confidence = Column(Float, nullable=False, default=0.85)

    # Relationships
    event = relationship("Event", backref="framing_analyses")

    def get_sources_list(self) -> list[str]:
        try:
            return json.loads(self.sources_analyzed) if self.sources_analyzed else []
        except Exception:
            return []

    def get_comparisons_list(self) -> list[dict]:
        try:
            return json.loads(self.comparisons) if self.comparisons else []
        except Exception:
            return []

    def get_framing_patterns_list(self) -> list[str]:
        try:
            return json.loads(self.framing_patterns) if self.framing_patterns else []
        except Exception:
            return []

    def get_language_patterns_list(self) -> list[str]:
        try:
            return json.loads(self.language_patterns) if self.language_patterns else []
        except Exception:
            return []

    def get_areas_of_agreement_list(self) -> list[str]:
        try:
            return json.loads(self.areas_of_agreement) if self.areas_of_agreement else []
        except Exception:
            return []

    def get_areas_of_difference_list(self) -> list[str]:
        try:
            return json.loads(self.areas_of_difference) if self.areas_of_difference else []
        except Exception:
            return []
