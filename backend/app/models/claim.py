"""Claim and Evidence ORM models for the Fact-Checking and Verification Agent.

Provides complete evidence traceability:
Claim -> Evidence -> Source -> NLI Result -> Corroboration Score -> Verdict
"""

import enum
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ClaimType(str, enum.Enum):
    FACTUAL = "FACTUAL"
    ATTRIBUTION = "ATTRIBUTION"
    NUMERICAL = "NUMERICAL"
    PREDICTION = "PREDICTION"
    OPINION = "OPINION"


class VerificationVerdict(str, enum.Enum):
    WELL_SUPPORTED = "WELL_SUPPORTED"
    DISPUTED = "DISPUTED"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"


class Claim(Base, TimestampMixin, UUIDMixin):
    """An atomic extracted claim undergoing fact-checking verification."""
    __tablename__ = "claims"

    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True)
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=True, index=True)

    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(50), default="FACTUAL", nullable=False)  # FACTUAL, ATTRIBUTION, NUMERICAL, PREDICTION, OPINION
    verdict = Column(String(50), default="UNVERIFIED", nullable=False)  # WELL_SUPPORTED, DISPUTED, UNVERIFIED, CONTRADICTED
    confidence = Column(Float, default=0.5, nullable=False)

    independent_sources = Column(Integer, default=0, nullable=False)
    source_reliability = Column(Float, default=0.5, nullable=False)

    # Relationships
    evidence = relationship("ClaimEvidence", back_populates="claim", cascade="all, delete-orphan")
    event = relationship("Event", backref="claims")
    article = relationship("Article", backref="claims")


class ClaimEvidence(Base, TimestampMixin, UUIDMixin):
    """External or internal evidence retrieved for a claim, with NLI stance classification."""
    __tablename__ = "claim_evidence"

    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)

    source_name = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=True)
    passage = Column(Text, nullable=False)
    publication_date = Column(String(50), nullable=True)

    source_reliability = Column(Float, default=0.8, nullable=False)
    retrieval_score = Column(Float, default=0.8, nullable=False)

    nli_stance = Column(String(50), default="NEUTRAL", nullable=False)  # SUPPORTS, REFUTES, NEUTRAL
    nli_confidence = Column(Float, default=0.5, nullable=False)
    independence_weight = Column(Float, default=1.0, nullable=False)

    # Relationship
    claim = relationship("Claim", back_populates="evidence")
