"""Celery task worker for automated event summarization."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.pipeline.celery_app import celery_app
from app.schemas.event import EventSummaryLength
from app.services.event_summarizer_service import EventSummarizerService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=20)
def generate_event_summary_task(self, event_id: str, length: str = "standard", force: bool = False):
    """Asynchronously synthesize and persist an event cluster summary."""
    try:
        result = asyncio.run(_run_summarize(event_id, length, force))
        logger.info("Successfully generated summary for event %s", event_id)
        return result
    except Exception as exc:
        logger.error("Failed to generate summary for event %s: %s", event_id, exc)
        raise self.retry(exc=exc) from exc


async def _run_summarize(event_id: str, length: str, force: bool) -> dict:
    len_enum = EventSummaryLength(length) if length in {"flash", "standard", "detailed"} else EventSummaryLength.STANDARD
    async with EventSummarizerService() as service:
        res = await service.summarize_event_by_id(UUID(event_id), length=len_enum, force_regenerate=force)
        return res.model_dump()
