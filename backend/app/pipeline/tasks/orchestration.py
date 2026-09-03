"""Celery tasks for orchestrator pipeline execution.

WHY Celery tasks for the orchestrator:
- Enables distributed processing across multiple workers.
- Provides automatic retries, rate limiting, and monitoring.
- Integrates with the existing Celery infrastructure.
- Beat scheduler can trigger periodic reprocessing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=600,  # 10 minutes
    time_limit=660,
)
def process_event(self, event_id: str, article_ids: list[str] | None = None) -> dict:
    """Main orchestrator task: process an event through the full pipeline.

    This is the primary entry point for the orchestrator.
    Called when new articles arrive or when reprocessing is triggered.
    """
    try:
        return asyncio.run(_process_event_async(event_id, article_ids))
    except Exception as exc:
        logger.error(f"Orchestration failed for event {event_id}: {exc}")
        raise self.retry(exc=exc) from exc


async def _process_event_async(
    event_id: str,
    article_ids: list[str] | None = None,
) -> dict:
    """Async implementation of event processing."""
    from app.pipeline.orchestrator.graph import OrchestratorGraph
    from app.pipeline.orchestrator.state import EventProcessingState, ArticleInfo

    # Load existing state or create new
    state = await _load_or_create_state(event_id, article_ids)

    # Run the orchestrator graph
    orchestrator = OrchestratorGraph()
    final_state = await orchestrator.process_with_retry(state)

    # Persist the final state
    await _persist_state(final_state)

    return {
        "event_id": final_state.event_id,
        "status": final_state.status,
        "confidence": final_state.confidence,
        "processing_time_ms": final_state.processing_metadata.total_processing_time_ms,
        "agents_invoked": final_state.processing_metadata.agents_invoked,
    }


async def _load_or_create_state(
    event_id: str,
    article_ids: list[str] | None = None,
) -> EventProcessingState:
    """Load existing state from Redis or create a new one."""
    from app.pipeline.orchestrator.state import EventProcessingState, ArticleInfo

    # Try to load from Redis checkpoint
    state = await _load_checkpoint(event_id)
    if state:
        return state

    # Create new state
    return EventProcessingState(
        event_id=event_id,
        article_ids=article_ids or [],
    )


async def _load_checkpoint(event_id: str) -> EventProcessingState | None:
    """Load state from Redis checkpoint."""
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings

        redis = aioredis.from_url(settings.redis_url)
        key = f"orchestrator:checkpoint:{event_id}"
        data = await redis.get(key)
        await redis.aclose()

        if data:
            import json
            return EventProcessingState.from_checkpoint(json.loads(data))
    except Exception as exc:
        logger.debug(f"Could not load checkpoint for {event_id}: {exc}")
    return None


async def _persist_state(state: EventProcessingState) -> None:
    """Persist state to Redis checkpoint."""
    try:
        import json

        import redis.asyncio as aioredis
        from app.core.config import settings

        redis = aioredis.from_url(settings.redis_url)
        key = f"orchestrator:checkpoint:{state.event_id}"
        data = json.dumps(state.to_checkpoint())
        await redis.set(key, data, ex=86400)  # 24h TTL
        await redis.aclose()
    except Exception as exc:
        logger.warning(f"Could not persist checkpoint for {state.event_id}: {exc}")


@celery_app.task(bind=True, max_retries=2)
def process_single_agent(
    self,
    agent_name: str,
    event_id: str,
    payload: dict,
) -> dict:
    """Process a single agent for an event.

    Used for targeted reprocessing (e.g., re-run only the summarizer).
    """
    try:
        return asyncio.run(_process_single_agent_async(agent_name, event_id, payload))
    except Exception as exc:
        logger.error(f"Agent '{agent_name}' failed for event {event_id}: {exc}")
        raise self.retry(exc=exc) from exc


async def _process_single_agent_async(
    agent_name: str,
    event_id: str,
    payload: dict,
) -> dict:
    """Async implementation of single agent processing."""
    from app.pipeline.orchestrator.registry import get_registry
    from app.pipeline.orchestrator.schemas import AgentTaskPayload

    registry = get_registry()
    handler = registry.get_handler(agent_name)
    if handler is None:
        return {"error": f"Agent '{agent_name}' not registered"}

    task_payload = AgentTaskPayload(**payload)
    result = await handler(task_payload)

    if isinstance(result, dict):
        return result
    elif hasattr(result, "model_dump"):
        return result.model_dump()
    return {}


@celery_app.task(bind=True, max_retries=2)
def reprocess_event(
    self,
    event_id: str,
    from_stage: str | None = None,
) -> dict:
    """Reprocess an event from a specific stage.

    WHY reprocessing:
    - New articles arrive for an existing event.
    - An agent's output needs to be updated.
    - Manual trigger by an admin.
    """
    try:
        return asyncio.run(_reprocess_event_async(event_id, from_stage))
    except Exception as exc:
        logger.error(f"Reprocessing failed for event {event_id}: {exc}")
        raise self.retry(exc=exc) from exc


async def _reprocess_event_async(
    event_id: str,
    from_stage: str | None = None,
) -> dict:
    """Async implementation of event reprocessing."""
    from app.pipeline.orchestrator.graph import OrchestratorGraph
    from app.pipeline.orchestrator.idempotency import DeduplicationChecker
    from app.pipeline.orchestrator.state import EventProcessingState, EventStatus

    # Load existing state
    state = await _load_checkpoint(event_id)
    if state is None:
        return {"error": f"No state found for event {event_id}"}

    # Reset status to allow reprocessing
    if from_stage:
        # Set status to the stage before the target
        stage_order = [
            "ingestion", "deduplication", "clustering", "classification",
            "domain_analysis", "summarization", "verification",
            "bias_framing", "embedding", "completed",
        ]
        if from_stage in stage_order:
            idx = stage_order.index(from_stage) - 1
            if idx >= 0:
                # Set to the status corresponding to the previous stage
                from app.pipeline.orchestrator.routing import STAGE_TO_STATUS
                prev_stage = stage_order[idx]
                if prev_stage in STAGE_TO_STATUS:
                    state.status = STAGE_TO_STATUS[prev_stage]
    else:
        state.status = EventStatus.NEW

    state.retry_count = 0
    state.last_error = None
    state.processing_metadata.is_reprocessing = True
    state.processing_metadata.trigger = "manual"

    # Run the orchestrator
    orchestrator = OrchestratorGraph()
    final_state = await orchestrator.process(state)

    # Persist
    await _persist_state(final_state)

    return {
        "event_id": final_state.event_id,
        "status": final_state.status,
        "reprocessing_complete": True,
    }


@celery_app.task
def get_orchestrator_status() -> dict:
    """Get the current status of the orchestrator."""
    from app.pipeline.orchestrator.registry import get_registry
    from app.pipeline.orchestrator.priority import PriorityQueue

    registry = get_registry()

    return {
        "registered_agents": registry.get_agent_names(),
        "agent_count": registry.agent_count,
        "status": "healthy",
    }
