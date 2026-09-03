"""Multi-Agent Orchestrator for NewsSense AI.

Central coordinator that routes articles through the processing pipeline,
manages agent lifecycle, handles failures, and ensures idempotent processing.

Architecture:
    LangGraph manages the workflow graph (nodes = agent stages, edges = routing).
    Celery distributes agent tasks across workers.
    Redis provides locks for idempotency and pub/sub for status updates.
    PostgreSQL stores execution history via the AgentRun model.

Graph Topology:
    ingestion → deduplication → clustering → classification
    → domain_analysis (fan-out to N agents in parallel)
    → summarization → verification (claims → evidence → NLI → corroboration)
    → bias_framing → embedding → completion

    With conditional edges for human review and failure handling.
"""

from app.pipeline.orchestrator.graph import OrchestratorGraph
from app.pipeline.orchestrator.registry import AgentRegistry, get_registry
from app.pipeline.orchestrator.state import (
    EventProcessingState,
    EventPriority,
    EventStatus,
)

__all__ = [
    "OrchestratorGraph",
    "AgentRegistry",
    "EventProcessingState",
    "EventPriority",
    "EventStatus",
    "get_registry",
]
