"""Repository for AgentRun persistence and querying.

WHY a dedicated repository:
- Follows the existing project pattern (separate repository layer).
- Enables querying agent performance metrics (avg latency, error rates).
- Supports filtering by event, agent, status, and time range.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class AgentRunRepository(BaseRepository[AgentRun]):
    """Repository for agent execution history."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, AgentRun)

    async def create_run(
        self,
        event_id: str,
        agent_name: str,
        pipeline_run_id: str,
        processing_version: str = "1.0.0",
        status: str = "pending",
        input_article_ids: list[str] | None = None,
    ) -> AgentRun:
        """Create a new agent run record."""
        run = AgentRun(
            event_id=event_id,
            agent_name=agent_name,
            pipeline_run_id=pipeline_run_id,
            processing_version=processing_version,
            status=status,
            input_article_ids=input_article_ids or [],
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def update_run_status(
        self,
        run_id: Any,
        status: str,
        *,
        confidence: float | None = None,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        error_type: str | None = None,
        error_category: str | None = None,
        processing_time_ms: float | None = None,
        model_used: str | None = None,
        token_usage: dict[str, int] | None = None,
    ) -> AgentRun | None:
        """Update an agent run's status and results."""
        run = await self.get_by_id(run_id)
        if not run:
            return None

        run.status = status
        if status == "running":
            run.started_at = datetime.utcnow().isoformat()
        elif status in ("completed", "failed", "skipped"):
            run.completed_at = datetime.utcnow().isoformat()

        if confidence is not None:
            run.confidence = confidence
        if output is not None:
            run.output = output
        if error is not None:
            run.error = error
        if error_type is not None:
            run.error_type = error_type
        if error_category is not None:
            run.error_category = error_category
        if processing_time_ms is not None:
            run.processing_time_ms = processing_time_ms
        if model_used is not None:
            run.model_used = model_used
        if token_usage is not None:
            run.token_usage = token_usage

        await self.db.flush()
        return run

    async def get_by_event(self, event_id: str) -> list[AgentRun]:
        """Get all agent runs for a specific event."""
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.event_id == event_id)
            .order_by(AgentRun.created_at)
        )
        return list(result.scalars().all())

    async def get_by_pipeline_run(self, pipeline_run_id: str) -> list[AgentRun]:
        """Get all agent runs for a specific pipeline execution."""
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.pipeline_run_id == pipeline_run_id)
            .order_by(AgentRun.created_at)
        )
        return list(result.scalars().all())

    async def get_by_status(self, status: str, limit: int = 100) -> list[AgentRun]:
        """Get agent runs by status."""
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.status == status)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_failed_runs(
        self,
        event_id: str | None = None,
        agent_name: str | None = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        """Get failed agent runs, optionally filtered by event or agent."""
        query = select(AgentRun).where(AgentRun.status == "failed")
        if event_id:
            query = query.where(AgentRun.event_id == event_id)
        if agent_name:
            query = query.where(AgentRun.agent_name == agent_name)
        query = query.order_by(AgentRun.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_agent_performance(
        self,
        agent_name: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get performance metrics for a specific agent."""
        # This is a simplified version; production would use more complex aggregations
        result = await self.db.execute(
            select(
                func.count(AgentRun.id).label("total_runs"),
                func.avg(AgentRun.processing_time_ms).label("avg_latency_ms"),
                func.avg(AgentRun.confidence).label("avg_confidence"),
            )
            .where(AgentRun.agent_name == agent_name)
            .where(AgentRun.status == "completed")
        )
        row = result.one_or_none()

        failed_result = await self.db.execute(
            select(func.count(AgentRun.id))
            .where(AgentRun.agent_name == agent_name)
            .where(AgentRun.status == "failed")
        )
        failed_count = failed_result.scalar() or 0

        total = (row.total_runs if row else 0) + failed_count
        return {
            "agent_name": agent_name,
            "total_runs": total,
            "completed_runs": row.total_runs if row else 0,
            "failed_runs": failed_count,
            "error_rate": failed_count / total if total > 0 else 0.0,
            "avg_latency_ms": float(row.avg_latency_ms or 0),
            "avg_confidence": float(row.avg_confidence or 0),
        }
