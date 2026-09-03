"""Celery / background task worker for article deduplication and event clustering."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.pipeline.celery_app import celery_app
from app.services.dedup_clustering_service import DedupClusteringService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_article_clustering(self, article_id: str):
    """Asynchronously evaluate article for exact duplicates, near duplicates, syndication, and event clusters."""
    try:
        result = asyncio.run(_run_clustering(article_id))
        logger.info("Clustered article %s: %s", article_id, result)
        return result
    except Exception as exc:
        logger.error("Failed to cluster article %s: %s", article_id, exc)
        raise self.retry(exc=exc) from exc


async def _run_clustering(article_id: str) -> dict:
    async with DedupClusteringService() as service:
        match_result = await service.process_article(UUID(article_id))
        return match_result.model_dump()
