"""SQLAlchemy Model for Vector Document Embedding Tracking and Audit.

Maintains relational metadata and audit trails alongside the high-performance
vector store (Qdrant), guaranteeing content hash deduplication, versioning,
and transactional traceability across Articles, Events, Claims, and Evidence.
"""

from __future__ import annotations

import json
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin, UUIDMixin


class DocumentEmbedding(Base, TimestampMixin, UUIDMixin):
    """Tracks document embeddings, content hashes, and vector points."""
    __tablename__ = "document_embeddings"

    document_id = Column(String(100), nullable=False, index=True)
    document_type = Column(String(50), nullable=False, index=True)  # article, event_summary, claim, evidence, entity, topic
    point_id = Column(String(150), unique=True, nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of text to prevent re-embedding
    embedding_version = Column(String(50), default="v1-all-MiniLM-L6-v2", nullable=False)
    document_version = Column(Integer, default=1, nullable=False)

    # Search & Filtering metadata fields
    event_id = Column(String(100), nullable=True, index=True)
    article_id = Column(String(100), nullable=True, index=True)
    source_id = Column(String(100), nullable=True, index=True)
    category = Column(String(50), nullable=True, index=True)
    country = Column(String(10), nullable=True, index=True)
    language = Column(String(10), default="en", nullable=False)
    published_at = Column(String(50), nullable=True)
    verification_status = Column(String(50), nullable=True, index=True)  # WELL_SUPPORTED, DISPUTED, UNVERIFIED, CONTRADICTED

    # JSON stored attributes
    entities_json = Column(Text, default="[]", nullable=False)
    topics_json = Column(Text, default="[]", nullable=False)
    raw_payload_json = Column(Text, default="{}", nullable=False)

    def get_entities(self) -> list[str]:
        try:
            return json.loads(self.entities_json or "[]")
        except Exception:
            return []

    def get_topics(self) -> list[str]:
        try:
            return json.loads(self.topics_json or "[]")
        except Exception:
            return []

    def get_raw_payload(self) -> dict:
        try:
            return json.loads(self.raw_payload_json or "{}")
        except Exception:
            return {}
