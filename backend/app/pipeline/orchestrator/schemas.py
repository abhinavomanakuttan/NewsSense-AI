"""Structured schemas for inter-agent communication.

WHY strict schemas:
- Prevents agents from passing arbitrary uncontrolled data.
- Ensures every message has the required metadata (event_id, agent, timestamp).
- Makes debugging easier: every message is self-describing.
- Prevents schema drift when new agents are added.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentTaskPayload(BaseModel):
    """Payload sent to an agent via Celery or direct invocation.

    This is the INPUT to every agent. Agents must consume this schema
    and nothing else.
    """
    event_id: str
    article_ids: list[str] = Field(default_factory=list)
    articles: list[dict[str, Any]] = Field(default_factory=list)
    agent_name: str
    processing_version: str = "1.0.0"

    # Optional context from previous agents
    classification: dict[str, Any] | None = None
    domain_analyses: list[dict[str, Any]] | None = None
    claims: list[dict[str, Any]] | None = None
    summary: str | None = None

    # Processing hints
    priority: str = "normal"
    is_reprocessing: bool = False
    trigger: str | None = None  # new_article, manual, scheduled

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])


class AgentTaskResult(BaseModel):
    """Structured output from an agent execution.

    Every agent MUST return this schema. The orchestrator will reject
    any result that doesn't conform.
    """
    event_id: str
    agent_name: str
    status: str  # completed, failed, skipped
    confidence: float = 0.0

    # The actual output (agent-specific)
    output: dict[str, Any] = Field(default_factory=dict)

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_time_ms: float = 0.0

    # Error info
    error: str | None = None
    error_type: str | None = None

    # Model info
    model_used: str | None = None
    token_usage: dict[str, int] | None = None

    # Retry info
    retry_count: int = 0
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])


class OrchestratorCommand(BaseModel):
    """Command from the orchestrator to trigger an agent.

    Used internally by the LangGraph nodes to dispatch work.
    """
    command: str  # process, retry, skip, fail, reprocess
    event_id: str
    agent_name: str
    payload: AgentTaskPayload | None = None
    reason: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventUpdateMessage(BaseModel):
    """Message for when a new article arrives for an existing event.

    WHY a dedicated message:
    - The orchestrator needs to know what changed to decide
      which downstream agents to re-invoke.
    - Prevents unnecessary full reprocessing.
    """
    event_id: str
    new_article_ids: list[str]
    existing_article_count: int
    trigger: str = "new_article"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineStatusMessage(BaseModel):
    """Status update published to Redis pub/sub for real-time monitoring."""
    event_id: str
    status: str
    current_stage: str | None = None
    confidence: float | None = None
    progress_pct: float | None = None  # 0-100
    message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
