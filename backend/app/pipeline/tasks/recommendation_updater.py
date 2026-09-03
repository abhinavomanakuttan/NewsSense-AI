import asyncio
import logging
from uuid import UUID

from app.ai.recommender import ArticleRecommender
from app.db.session import async_session_factory
from app.pipeline.celery_app import celery_app
from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.services.recommendation_service import (
    TRENDING_CACHE_KEY,
    RecommendationService,
)
from app.utils.cache import cache_service

logger = logging.getLogger(__name__)


@celery_app.task
def update_trending() -> dict:
    return asyncio.run(_update_trending())


async def _update_trending() -> dict:
    async with async_session_factory() as session:
        repo = ArticleRepository(session)
        articles = await repo.get_trending(limit=50)

        trending = [
            {
                "id": str(a.id),
                "title": a.title,
                "slug": a.slug,
                "view_count": a.view_count,
                "credibility_score": a.credibility_score,
                "published_at": a.published_at,
                "source_name": a.source.name if a.source else None,
                "category_name": a.category.name if a.category else None,
                "image_url": a.image_url,
            }
            for a in articles
        ]

    await cache_service.initialize()
    try:
        await cache_service.set(TRENDING_CACHE_KEY, trending, ttl=1800)
        logger.info(f"Trending cache updated with {len(trending)} articles")
        return {"status": "trending_updated", "count": len(trending)}
    except Exception as exc:
        logger.warning(f"Redis unavailable; trending cache not persisted: {exc}")
        return {"status": "trending_updated", "count": len(trending), "cached": False}


@celery_app.task
def update_user_recommendations(user_id: str) -> dict:
    return asyncio.run(_update_user_recommendations(user_id))


async def _update_user_recommendations(user_id: str) -> dict:
    async with async_session_factory() as session:
        service = RecommendationService(
            article_repo=ArticleRepository(session),
            preference_repo=UserPreferenceRepository(session),
            reading_history_repo=ReadingHistoryRepository(session),
            bookmark_repo=BookmarkRepository(session),
            recommender=ArticleRecommender(),
        )
        recommendations = await service.get_recommendations(
            UUID(user_id), limit=20, use_cache=False
        )

    payload = [r.model_dump(mode="json") for r in recommendations]

    await cache_service.initialize()
    try:
        await cache_service.set(f"recommendations:user:{user_id}", payload, ttl=1800)
        return {"user_id": user_id, "status": "updated", "count": len(payload)}
    except Exception as exc:
        logger.warning(f"Redis unavailable; recommendations not cached: {exc}")
        return {"user_id": user_id, "status": "updated", "count": len(payload), "cached": False}
