import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.source import Source
from app.pipeline.celery_app import celery_app
from app.services.article_ingestion_service import ArticleIngestionService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_source(self, source_id: str):
    """Fetch and persist articles for one source, best-effort."""
    try:
        result = asyncio.run(_ingest_source(source_id))
        logger.info(f"Ingested source {source_id}: {result}")
        _dispatch_enrichment(result)
        return result
    except Exception as exc:
        logger.error(f"Failed to ingest source {source_id}: {exc}")
        raise self.retry(exc=exc) from exc


async def _ingest_source(source_id: str) -> dict:
    async with ArticleIngestionService() as service:
        return await service.ingest_source(UUID(source_id))


def _dispatch_enrichment(result: dict) -> None:
    from app.core.config import settings

    if not settings.enable_enrichment:
        return
    from app.pipeline.tasks.enrichment import enrich_article

    for article_id in result.get("new_article_ids", []):
        try:
            enrich_article.delay(article_id)
        except Exception as exc:
            logger.warning(f"Failed to queue enrichment for {article_id}: {exc}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def fetch_all_feeds(self):
    """Query all active sources and dispatch one fetch task per source."""
    try:
        result = asyncio.run(_dispatch_all_sources())
        logger.info(f"Dispatched feed fetches: {result}")
        return result
    except Exception as exc:
        logger.error(f"fetch_all_feeds failed: {exc}")
        raise self.retry(exc=exc) from exc


async def _dispatch_all_sources() -> dict:
    async with async_session_factory() as session:
        result = await session.execute(select(Source).where(Source.is_active))
        sources = list(result.scalars().all())
        source_ids = [str(s.id) for s in sources]
        session.expunge_all()

    for source_id in source_ids:
        fetch_source.delay(source_id)

    return {"dispatched": len(source_ids), "source_ids": source_ids}


async def _dispatch_sources_by_priority(priority: str | None = None) -> dict:
    async with async_session_factory() as session:
        query = select(Source).where(Source.is_active)
        if priority:
            query = query.where(Source.priority == priority)
        result = await session.execute(query)
        sources = list(result.scalars().all())
        source_ids = [str(s.id) for s in sources]
        session.expunge_all()

    for source_id in source_ids:
        fetch_source.delay(source_id)

    return {"priority": priority or "all", "dispatched": len(source_ids), "source_ids": source_ids}


@celery_app.task(bind=True)
def fetch_high_priority_feeds(self):
    """Dispatch high-priority (breaking news) sources every 1-2 minutes."""
    result = asyncio.run(_dispatch_sources_by_priority("high"))
    logger.info(f"Dispatched high-priority sources: {result}")
    return result


@celery_app.task(bind=True)
def fetch_normal_priority_feeds(self):
    """Dispatch normal-priority sources every 5-15 minutes."""
    result = asyncio.run(_dispatch_sources_by_priority("normal"))
    logger.info(f"Dispatched normal-priority sources: {result}")
    return result


@celery_app.task(bind=True)
def fetch_low_priority_feeds(self):
    """Dispatch low-priority sources every 30-60 minutes."""
    result = asyncio.run(_dispatch_sources_by_priority("low"))
    logger.info(f"Dispatched low-priority sources: {result}")
    return result


# Backward-compatible wrapper kept for the original beat schedule name.
@celery_app.task
def fetch_rss_feed(feed_url: str, source_id: str):
    return fetch_source(source_id)


@celery_app.task(bind=True)
def fetch_newsapi(self, query: str = "latest", page_size: int = 50):
    """NewsAPI ingestion task using NewsApiClient."""
    from app.pipeline.news_api_client import NewsApiClient

    client = NewsApiClient()
    entries = asyncio.run(client.fetch_news_api(endpoint="https://newsapi.org/v2/top-headlines", query=query, page_size=page_size))
    return {"status": "success", "fetched": len(entries), "query": query}

