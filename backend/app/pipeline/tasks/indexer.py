import asyncio
import logging
from uuid import UUID

from app.db.session import async_session_factory
from app.pipeline.celery_app import celery_app
from app.repositories.article_repository import ArticleRepository
from app.services.elasticsearch_service import (
    build_article_document,
    get_elasticsearch_service,
)

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def index_article(self, article_data: dict) -> dict:
    """Index an article into Elasticsearch (full-text search index)."""

    async def _run():
        es = get_elasticsearch_service()
        if not await es.is_available():
            return {
                "article_id": article_data.get("id"),
                "indexed": False,
                "reason": "elasticsearch_unavailable",
            }

        article_id = article_data.get("id")
        if not article_id:
            return {"article_id": None, "indexed": False, "error": "no id"}

        async with async_session_factory() as session:
            repo = ArticleRepository(session)
            article = await repo.get_by_id(UUID(str(article_id)))
            if not article:
                return {"article_id": article_id, "indexed": False, "error": "not found"}

            document = build_article_document(article)
            ok = await es.index_document(str(article.id), document)
            if not ok:
                return {"article_id": article_id, "indexed": False, "error": "index failed"}

        return {
            "article_id": article_id,
            "indexed": True,
            "index": "articles",
            "es": True,
        }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"Indexing failed for {article_data.get('id')}: {exc}")
        raise self.retry(exc=exc) from exc


@celery_app.task
def remove_from_index(article_id: str) -> dict:
    async def _run():
        es = get_elasticsearch_service()
        removed = await es.delete_document(article_id) if await es.is_available() else False
        return {
            "article_id": article_id,
            "removed": removed,
            "elasticsearch_available": await es.is_available(),
        }

    return asyncio.run(_run())
