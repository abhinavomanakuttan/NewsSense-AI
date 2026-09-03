"""API endpoints for orchestrator control and monitoring.

WHY API endpoints:
- Admins need visibility into pipeline status and agent health.
- Trigger manual reprocessing for specific events.
- Monitor queue depth and processing metrics.
- Register/unregister agents at runtime (for dynamic scaling).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_admin_user
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class ProcessEventRequest(BaseModel):
    event_id: str
    article_ids: list[str] = Field(default_factory=list)
    priority: str = "normal"


class ReprocessEventRequest(BaseModel):
    event_id: str
    from_stage: str | None = None


class ProcessArticlesRequest(BaseModel):
    event_id: str
    new_article_ids: list[str]
    existing_article_count: int = 0


class OrchestratorStatusResponse(BaseModel):
    status: str
    registered_agents: list[str]
    agent_count: int
    queue_size: int
    timestamp: str


class EventStatusResponse(BaseModel):
    event_id: str
    status: str
    priority: str
    current_stage: str | None = None
    confidence: float
    retry_count: int
    agents_invoked: list[str]
    processing_time_ms: float
    created_at: str
    updated_at: str
    completed_at: str | None = None
    last_error: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=OrchestratorStatusResponse)
async def get_orchestrator_status(
    admin: Any = Depends(get_current_admin_user),
) -> OrchestratorStatusResponse:
    """Get orchestrator health and status."""
    async with OrchestratorService() as svc:
        status = await svc.get_pipeline_status()
    return OrchestratorStatusResponse(**status)


@router.post("/process")
async def process_event(
    request: ProcessEventRequest,
    admin: Any = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Trigger event processing through the full pipeline."""
    async with OrchestratorService() as svc:
        result = await svc.process_event(
            event_id=request.event_id,
            article_ids=request.article_ids,
            priority=request.priority,
        )
    return result


@router.post("/reprocess")
async def reprocess_event(
    request: ReprocessEventRequest,
    admin: Any = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Reprocess an event from a specific stage."""
    from app.pipeline.tasks.orchestration import reprocess_event as reprocess_task

    task = reprocess_task.delay(request.event_id, request.from_stage)
    return {
        "task_id": task.id,
        "event_id": request.event_id,
        "status": "queued",
    }


@router.post("/articles")
async def process_new_articles(
    request: ProcessArticlesRequest,
    admin: Any = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Handle new articles arriving for an existing event."""
    async with OrchestratorService() as svc:
        result = await svc.process_new_articles(
            event_id=request.event_id,
            new_article_ids=request.new_article_ids,
            existing_article_count=request.existing_article_count,
        )
    return result


@router.get("/events/{event_id}/status")
async def get_event_status(
    event_id: str,
    admin: Any = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Get the processing status of a specific event."""
    async with OrchestratorService() as svc:
        status = await svc.get_event_status(event_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Event not found in orchestrator state")
    return status


@router.get("/queue")
async def get_queue_status(
    count: int = 10,
    admin: Any = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Peek at the top events in the processing queue."""
    async with OrchestratorService() as svc:
        top = await svc.get_queue_top(count)
    return {
        "queue": top,
        "count": len(top),
    }


@router.get("/agents")
async def list_agents(
    admin: Any = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """List all registered agents and their capabilities."""
    from app.pipeline.orchestrator.registry import get_registry

    registry = get_registry()
    agents = registry.get_all_agents()

    return {
        "agents": [
            {
                "name": a.name,
                "display_name": a.display_name,
                "description": a.description,
                "categories": a.categories,
                "is_critical": a.is_critical,
                "timeout_seconds": a.timeout_seconds,
                "max_retries": a.max_retries,
            }
            for a in agents
        ],
        "total": len(agents),
    }


@router.get("/metrics")
async def get_pipeline_metrics(
    admin: Any = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Get pipeline performance metrics."""
    from app.db.session import async_session_factory
    from app.repositories.agent_run_repository import AgentRunRepository

    async with async_session_factory() as session:
        repo = AgentRunRepository(session)

        # Get metrics for all registered agents
        from app.pipeline.orchestrator.registry import get_registry
        registry = get_registry()

        metrics = {}
        for agent_name in registry.get_agent_names():
            metrics[agent_name] = await repo.get_agent_performance(agent_name)

    return {
        "agent_metrics": metrics,
        "timestamp": "generated",
    }
