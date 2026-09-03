"""Pydantic Schemas for Vector Store, Semantic Memory, and Hybrid Search."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class VectorMetadata(BaseModel):
    """Metadata attributes associated with each vector point."""
    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(description="Unique entity ID (article_id, event_id, claim_id, etc.)")
    document_type: str = Field(description="Type: article, event_summary, claim, evidence, entity, topic")
    event_id: str | None = None
    article_id: str | None = None
    source_id: str | None = None
    category: str | None = None
    country: str | None = None
    language: str = "en"
    published_at: str | None = None
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    verification_status: str | None = Field(default=None, description="WELL_SUPPORTED, DISPUTED, UNVERIFIED, CONTRADICTED")
    title: str | None = None
    snippet: str | None = None
    content_hash: str | None = None
    embedding_version: str = "v1-all-MiniLM-L6-v2"


class VectorPointInput(BaseModel):
    """Input payload to embed and index a document into semantic memory."""
    document_id: str
    document_type: str  # article, event_summary, claim, evidence, entity, topic
    text: str = Field(description="The primary textual content to embed")
    metadata: VectorMetadata


class VectorSearchFilter(BaseModel):
    """Faceted filtering criteria applied during HNSW graph traversal."""
    document_types: list[str] | None = Field(default=None, description="Filter by doc types (e.g. ['claim', 'article'])")
    category: str | None = Field(default=None, description="Filter by news category (Technology, Politics, etc.)")
    country: str | None = Field(default=None, description="ISO country code (e.g. IN, US, UK)")
    language: str | None = Field(default=None, description="Language code")
    verification_status: str | None = Field(default=None, description="Filter claims/evidence by verdict")
    date_from: str | None = Field(default=None, description="ISO start date")
    date_to: str | None = Field(default=None, description="ISO end date")
    entities: list[str] | None = Field(default=None, description="Must match one or more entities")
    topics: list[str] | None = Field(default=None, description="Must match one or more topics")


class VectorSearchRequest(BaseModel):
    """Request query payload for dense or hybrid semantic search."""
    query: str = Field(description="Search query string")
    top_k: int = Field(default=10, ge=1, le=100)
    similarity_threshold: float | None = Field(default=0.20, ge=0.0, le=1.0)
    filter: VectorSearchFilter | None = None
    hybrid: bool = Field(default=True, description="Enable hybrid search combining dense similarity + lexical matching")
    alpha: float = Field(default=0.60, ge=0.0, le=1.0, description="Weight for dense retrieval in Reciprocal Rank Fusion")


class VectorSearchResult(BaseModel):
    """Individual retrieved result from semantic memory."""
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    document_type: str
    score: float = Field(description="Unified relevance score (RRF or Cosine)")
    dense_score: float | None = None
    lexical_score: float | None = None
    metadata: VectorMetadata
    text_snippet: str = ""

    def __getitem__(self, item: str) -> Any:
        if item == "id":
            return f"{self.document_type}_{self.document_id}"
        if item == "payload":
            return self.metadata.model_dump()
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except Exception:
            return default


class VectorSearchResponse(BaseModel):
    """Complete response payload for a semantic memory query."""
    query: str
    total_hits: int
    hybrid: bool
    results: list[VectorSearchResult]


class VectorStoreStatsResponse(BaseModel):
    """Operational statistics for semantic memory."""
    collection_name: str
    total_vectors: int
    document_type_counts: dict[str, int] = Field(default_factory=dict)
    embedding_model: str
    vector_dimension: int
    engine: str


class ReindexRequest(BaseModel):
    """Request to trigger document re-indexing into the vector store."""
    document_types: list[str] | None = Field(default=None, description="Specific types to reindex (default all)")
    force_all: bool = Field(default=False, description="If True, re-embed even if content_hash matches")


class ReindexResponse(BaseModel):
    """Response summary of the re-indexing job."""
    status: str
    indexed_count: int
    skipped_count: int
    duration_seconds: float
