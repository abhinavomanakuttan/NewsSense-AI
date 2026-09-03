"""Event processing state with a strict finite state machine.

WHY a dedicated state module:
- Every agent reads/writes to a single, validated state object.
- Invalid transitions are rejected at the type level.
- The state is serialisable to JSON for Redis checkpointing and DB persistence.
- No agent can silently corrupt the pipeline by writing arbitrary data.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Status enum — defines the finite state machine
# ---------------------------------------------------------------------------

class EventStatus(str, enum.Enum):
    """All possible statuses for an event in the processing pipeline.

    Valid transitions (enforced by `EventProcessingState.transition_to`):
        NEW             → INGESTED
        INGESTED        → DEDUPLICATED
        DEDUPLICATED    → CLUSTERED
        CLUSTERED       → CLASSIFIED
        CLASSIFIED      → ANALYZING | SUMMARIZING | VERIFYING | ANALYZING_FRAMING
        ANALYZING       → SUMMARIZING | VERIFYING | ANALYZING_FRAMING
        SUMMARIZING     → VERIFYING | ANALYZING_FRAMING
        VERIFYING       → ANALYZING_FRAMING | INDEXING | COMPLETED | REQUIRES_REVIEW
        ANALYZING_FRAMING → INDEXING | COMPLETED | REQUIRES_REVIEW
        INDEXING        → COMPLETED
        COMPLETED       → (terminal; can restart via reprocessing)
        FAILED          → (terminal; requires manual intervention or retry)
        REQUIRES_REVIEW → (terminal; requires human review)
    """

    NEW = "new"
    INGESTED = "ingested"
    DEDUPLICATED = "deduplicated"
    CLUSTERED = "clustered"
    CLASSIFIED = "classified"
    ANALYZING = "analyzing"            # Domain-specific analysis
    SUMMARIZING = "summarizing"
    VERIFYING = "verifying"            # Claim extraction → evidence → NLI → corroboration
    ANALYZING_FRAMING = "analyzing_framing"  # Bias / framing analysis
    INDEXING = "indexing"              # Embedding + vector store + ES
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


# Valid next-states for each status (exhaustive, no implicit transitions).
_VALID_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.NEW: {EventStatus.INGESTED},
    EventStatus.INGESTED: {EventStatus.DEDUPLICATED},
    EventStatus.DEDUPLICATED: {EventStatus.CLUSTERED},
    EventStatus.CLUSTERED: {EventStatus.CLASSIFIED},
    EventStatus.CLASSIFIED: {
        EventStatus.ANALYZING,
        EventStatus.SUMMARIZING,
        EventStatus.VERIFYING,
        EventStatus.ANALYZING_FRAMING,
        EventStatus.INDEXING,
        EventStatus.COMPLETED,
    },
    EventStatus.ANALYZING: {
        EventStatus.SUMMARIZING,
        EventStatus.VERIFYING,
        EventStatus.ANALYZING_FRAMING,
        EventStatus.INDEXING,
        EventStatus.COMPLETED,
    },
    EventStatus.SUMMARIZING: {
        EventStatus.VERIFYING,
        EventStatus.ANALYZING_FRAMING,
        EventStatus.INDEXING,
        EventStatus.COMPLETED,
    },
    EventStatus.VERIFYING: {
        EventStatus.ANALYZING_FRAMING,
        EventStatus.INDEXING,
        EventStatus.COMPLETED,
        EventStatus.REQUIRES_REVIEW,
    },
    EventStatus.ANALYZING_FRAMING: {
        EventStatus.INDEXING,
        EventStatus.COMPLETED,
        EventStatus.REQUIRES_REVIEW,
    },
    EventStatus.INDEXING: {EventStatus.COMPLETED},
    EventStatus.COMPLETED: set(),  # Terminal
    EventStatus.FAILED: set(),     # Terminal
    EventStatus.REQUIRES_REVIEW: set(),  # Terminal
}


# ---------------------------------------------------------------------------
# Priority enum
# ---------------------------------------------------------------------------

class EventPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    BREAKING = "breaking"

    @property
    def numeric(self) -> int:
        return {"low": 0, "normal": 1, "high": 2, "breaking": 3}[self.value]


# ---------------------------------------------------------------------------
# Pydantic sub-models for structured agent outputs
# ---------------------------------------------------------------------------

class ArticleInfo(BaseModel):
    """Metadata about a single article within an event."""
    id: str
    title: str
    url: str | None = None  # Optional — internal/test articles may not have a URL yet
    source_name: str | None = None
    source_domain: str | None = None  # Domain of the source publication
    source_credibility: float | None = None
    published_at: str | None = None
    content_hash: str | None = None
    language: str = "en"
    category_id: str | None = None


class ClaimInfo(BaseModel):
    """A factual claim extracted from articles."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str
    source_article_id: str | None = None
    claim_type: str | None = None  # factual, causal, temporal, etc.
    entities: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    """Evidence retrieved for a claim."""
    claim_id: str
    source_url: str | None = None
    snippet: str
    relevance_score: float = 0.0
    support_stance: str | None = None  # supports, refutes, neutral


class VerificationResult(BaseModel):
    """Result of verifying a single claim."""
    claim_id: str
    verdict: str  # verified, disputed, unverifiable, false
    confidence: float = 0.0
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    refuting_evidence: list[EvidenceItem] = Field(default_factory=list)


class BiasAnalysis(BaseModel):
    """Framing / bias analysis of an event."""
    overall_bias: str | None = None  # left, right, center, sensationalist, etc.
    bias_score: float = 0.0  # 0 = neutral, 1 = highly biased
    framing_patterns: list[str] = Field(default_factory=list)
    source_agreement_score: float = 0.0  # How much sources agree


class DomainAnalysis(BaseModel):
    """Output from a domain-specific agent."""
    domain: str
    confidence: float = 0.0
    subcategory: str | None = None
    key_entities: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Structured result from any agent execution."""
    agent_name: str
    status: str  # completed, failed, skipped
    confidence: float = 0.0
    output: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_time_ms: float = 0.0
    error: str | None = None
    retry_count: int = 0
    model_used: str | None = None
    token_usage: dict[str, int] | None = None


class ProcessingMetadata(BaseModel):
    """Metadata about how the event was processed."""
    processing_version: str = "1.0.0"
    pipeline_run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    total_processing_time_ms: float = 0.0
    agents_invoked: list[str] = Field(default_factory=list)
    agents_failed: list[str] = Field(default_factory=list)
    is_reprocessing: bool = False
    trigger: str | None = None  # new_article, manual, scheduled


# ---------------------------------------------------------------------------
# Main state model — the single source of truth for an event
# ---------------------------------------------------------------------------

class EventProcessingState(BaseModel):
    """Strongly-typed state for an event moving through the pipeline.

    WHY Pydantic BaseModel (not TypedDict):
    - Runtime validation on every field update.
    - Serialisable to/from JSON for Redis and DB storage.
    - Field-level validators catch data corruption early.
    - Model methods (transition_to, add_agent_result) enforce invariants.
    """

    # --- Identity ---
    event_id: str
    processing_version: str = "1.0.0"

    # --- Status machine ---
    status: EventStatus = EventStatus.NEW
    priority: EventPriority = EventPriority.NORMAL
    current_stage: str | None = None

    # --- Articles in this event ---
    article_ids: list[str] = Field(default_factory=list)
    articles: list[ArticleInfo] = Field(default_factory=list)

    # --- Classification ---
    category: str | None = None
    subcategory: str | None = None
    classification_confidence: float = 0.0

    # --- Domain analysis ---
    domain_analyses: list[DomainAnalysis] = Field(default_factory=list)

    # --- Claims & Verification ---
    claims: list[ClaimInfo] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)

    # --- Bias ---
    bias_analysis: BiasAnalysis | None = None

    # --- Summary ---
    summary: str | None = None

    # --- Embeddings ---
    embedding_status: str | None = None  # pending, completed, failed

    # --- Agent execution history ---
    agent_results: list[AgentResult] = Field(default_factory=list)
    agent_errors: list[dict[str, Any]] = Field(default_factory=list)

    # --- Confidence ---
    confidence: float = 0.0

    # --- Metadata ---
    processing_metadata: ProcessingMetadata = Field(default_factory=ProcessingMetadata)

    # --- Timestamps ---
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    # --- Error tracking ---
    retry_count: int = 0
    max_retries: int = 3
    last_error: str | None = None

    class Config:
        """Allow arbitrary types for datetime serialisation."""
        use_enum_values = True

    @field_validator("status", mode="before")
    @classmethod
    def _ensure_status_enum(cls, v: Any) -> Any:
        if isinstance(v, EventStatus):
            return v
        if isinstance(v, str):
            return EventStatus(v)
        return v

    def transition_to(self, new_status: EventStatus) -> None:
        """Attempt a state transition; raises ValueError on invalid transition.

        WHY strict transitions:
        - Prevents an event from jumping from NEW to COMPLETED.
        - Makes bugs in the routing logic fail loudly.
        - Creates an auditable trail of status changes.
        """
        current = EventStatus(self.status)
        valid = _VALID_TRANSITIONS.get(current, set())
        if new_status not in valid:
            raise ValueError(
                f"Invalid transition: {current.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in valid]}"
            )
        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def add_agent_result(self, result: AgentResult) -> None:
        """Append an agent's result and update aggregate confidence."""
        self.agent_results.append(result)
        self.updated_at = datetime.now(UTC)

        # Track failed agents
        if result.status == "failed":
            self.agent_errors.append({
                "agent": result.agent_name,
                "error": result.error,
                "timestamp": datetime.now(UTC).isoformat(),
            })

        # Update overall confidence (weighted average of successful agents)
        successful = [r for r in self.agent_results if r.status == "completed" and r.confidence > 0]
        if successful:
            self.confidence = sum(r.confidence for r in successful) / len(successful)

    def is_terminal(self) -> bool:
        """Check if the event is in a terminal state."""
        return EventStatus(self.status) in {
            EventStatus.COMPLETED,
            EventStatus.FAILED,
            EventStatus.REQUIRES_REVIEW,
        }

    def needs_retry(self) -> bool:
        """Check if the event can be retried."""
        return (
            EventStatus(self.status) == EventStatus.FAILED
            and self.retry_count < self.max_retries
        )

    def mark_failed(self, error: str) -> None:
        """Mark the event as failed with an error message."""
        self.status = EventStatus.FAILED
        self.last_error = error
        self.updated_at = datetime.now(UTC)

    def mark_completed(self) -> None:
        """Mark the event as completed."""
        self.status = EventStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def to_checkpoint(self) -> dict[str, Any]:
        """Serialize to a dict for LangGraph checkpointing."""
        return self.model_dump(mode="json")

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> EventProcessingState:
        """Deserialize from a checkpoint dict."""
        return cls.model_validate(data)
