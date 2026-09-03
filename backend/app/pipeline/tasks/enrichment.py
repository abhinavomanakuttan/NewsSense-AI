import asyncio
import logging

from app.pipeline.celery_app import celery_app
from app.services.article_enrichment_service import ArticleEnrichmentService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def enrich_article(self, article_id: str) -> dict:
    try:
        return asyncio.run(_enrich(article_id))
    except Exception as exc:
        logger.error(f"Enrichment failed for article {article_id}: {exc}")
        raise self.retry(exc=exc) from exc


async def _enrich(article_id: str) -> dict:
    async with ArticleEnrichmentService() as service:
        return await service.enrich_article(article_id)
