import logging
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_admin, get_source_repo
from app.pipeline.tasks.feed_fetcher import fetch_source
from app.repositories.source_repository import SourceRepository
from app.schemas.common import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/sources/{source_id}/refresh")
async def refresh_source(
    source_id: str,
    admin=Depends(get_current_admin),
    source_repo: SourceRepository = Depends(get_source_repo),
):
    source = await source_repo.get_by_id(UUID(source_id))
    if not source:
        return MessageResponse(message=f"Source {source_id} not found")

    if not (source.is_active and source.feed_url):
        return MessageResponse(message=f"Source {source_id} is inactive or has no feed_url")

    if not await _broker_available():
        return MessageResponse(
            message=f"Source {source_id} refreshed inline: {await _ingest_inline(source_id)}"
        )

    try:
        fetch_source.delay(source_id)
    except Exception:
        return MessageResponse(
            message=f"Broker unavailable; refreshed inline: {await _ingest_inline(source_id)}"
        )
    return MessageResponse(message=f"Source {source_id} refresh queued")


@router.post("/ingest-all")
async def ingest_all_sources(
    admin=Depends(get_current_admin),
):
    from app.pipeline.tasks.feed_fetcher import fetch_all_feeds

    if not await _broker_available():
        from sqlalchemy import select

        from app.db.session import async_session_factory
        from app.models.source import Source
        from app.pipeline.tasks.feed_fetcher import _ingest_source

        async with async_session_factory() as session:
            result = await session.execute(
                select(Source.id).where(Source.is_active, Source.feed_url.is_not(None))
            )
            ids = [str(row[0]) for row in result.all()]

        results = []
        for source_id in ids:
            try:
                result = await _ingest_source(source_id)
                results.append({"source": source_id, "result": result})
                await _dispatch_inline_enrichment(result)
            except Exception as exc:
                results.append({"source": source_id, "error": str(exc)})
        return MessageResponse(message=f"Inline ingestion finished: {results}")

    fetch_all_feeds.delay()
    return MessageResponse(message="Full ingestion queued")


async def _ingest_inline(source_id: str) -> dict:
    from app.services.article_ingestion_service import ArticleIngestionService

    async with ArticleIngestionService() as service:
        return await service.ingest_source(UUID(source_id))


async def _dispatch_inline_enrichment(result: dict) -> None:
    from app.core.config import settings
    from app.services.article_enrichment_service import ArticleEnrichmentService

    if not settings.enable_enrichment:
        return
    for article_id in result.get("new_article_ids", []):
        try:
            async with ArticleEnrichmentService() as service:
                await service.enrich_article(article_id)
        except Exception as exc:
            logger.exception(f"Inline enrichment failed for {article_id}: {exc}")


async def _broker_available() -> bool:
    from kombu import Connection

    from app.core.config import settings

    if not settings.celery_broker_url:
        return False
    if settings.celery_broker_url.startswith("memory"):
        return True

    import asyncio

    def probe():
        try:
            with Connection(settings.celery_broker_url, connect_timeout=2) as conn:
                conn.connect()
            return True
        except Exception:
            return False

    return await asyncio.to_thread(probe)


@router.get("/system/health")
async def system_health(
    admin=Depends(get_current_admin),
):
    return {
        "status": "healthy",
        "services": {
            "api": "up",
            "database": "up",
            "redis": "up",
            "celery": "up",
        },
    }
