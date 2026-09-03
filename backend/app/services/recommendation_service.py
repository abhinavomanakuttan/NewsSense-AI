import logging
from uuid import UUID

from app.ai.recommender import ArticleRecommender
from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.schemas.recommendation import RecommendationResponse
from app.utils.cache import cache_service

logger = logging.getLogger(__name__)

TRENDING_CACHE_KEY = "trending:top"
USER_RECS_CACHE_PREFIX = "recommendations:user:"
USER_RECS_TTL = 1800


async def invalidate_user_recommendations(user_id: UUID) -> None:
    """Drop the cached recommendation list for a user (best-effort).

    Called when a signal that feeds recommendations changes: preferences,
    reading history, or bookmarks.
    """
    try:
        await cache_service.initialize()
        await cache_service.delete(f"{USER_RECS_CACHE_PREFIX}{user_id}")
    except Exception as exc:
        logger.warning(f"Could not invalidate recommendations cache: {exc}")


def _keywords_of(article) -> str | None:
    return getattr(article, "keywords", None)


class RecommendationService:
    def __init__(
        self,
        article_repo: ArticleRepository,
        preference_repo: UserPreferenceRepository,
        reading_history_repo: ReadingHistoryRepository,
        recommender: ArticleRecommender | None = None,
        bookmark_repo: BookmarkRepository | None = None,
    ):
        self.article_repo = article_repo
        self.preference_repo = preference_repo
        self.reading_history_repo = reading_history_repo
        self.recommender = recommender or ArticleRecommender()
        self.bookmark_repo = bookmark_repo

    async def get_recommendations(
        self, user_id: UUID, limit: int = 20, use_cache: bool = True
    ) -> list[RecommendationResponse]:
        cached = await self._get_cached(user_id, limit) if use_cache else None
        if cached is not None:
            return cached

        recommendations = await self._compute_recommendations(user_id, limit)
        await self._set_cached(user_id, recommendations)
        return recommendations

    async def _get_cached(self, user_id: UUID, limit: int) -> list[RecommendationResponse] | None:
        try:
            await cache_service.initialize()
            cached = await cache_service.get(f"{USER_RECS_CACHE_PREFIX}{user_id}")
        except Exception as exc:
            logger.warning(f"Recommendations cache read failed: {exc}")
            return None
        if not cached:
            return None
        try:
            return [RecommendationResponse(**item) for item in cached][:limit]
        except Exception:
            return None

    async def _set_cached(
        self, user_id: UUID, recommendations: list[RecommendationResponse]
    ) -> None:
        payload = [r.model_dump(mode="json") for r in recommendations]
        try:
            await cache_service.initialize()
            await cache_service.set(
                f"{USER_RECS_CACHE_PREFIX}{user_id}", payload, ttl=USER_RECS_TTL
            )
        except Exception as exc:
            logger.warning(f"Recommendations cache write failed: {exc}")

    async def _compute_recommendations(
        self, user_id: UUID, limit: int
    ) -> list[RecommendationResponse]:
        prefs = await self.preference_repo.get_or_create(user_id)
        history = await self.reading_history_repo.get_user_history(user_id, limit=100)
        bookmarks = (
            await self.bookmark_repo.get_user_bookmarks(user_id, limit=100)
            if self.bookmark_repo
            else []
        )

        read_ids = {h.article_id for h in history} | {b.article_id for b in bookmarks}
        preferred_languages = prefs.preferred_languages or []

        articles = await self.article_repo.get_recommendation_candidates(
            limit=max(limit * 3, 60),
            excluded_ids=list(read_ids) or None,
            languages=preferred_languages or None,
        )
        if not articles:
            return []

        payload = [
            {
                "id": str(a.id),
                "title": a.title,
                "slug": a.slug,
                "summary": a.summary,
                "source_name": a.source.name if a.source else None,
                "category": a.category.name if a.category else None,
                "category_name": a.category.name if a.category else None,
                "credibility_score": a.credibility_score,
                "view_count": a.view_count,
                "published_at": a.published_at,
                "language": a.language,
                "keywords": _keywords_of(a),
                "image_url": a.image_url,
            }
            for a in articles
        ]

        user_preferences = {
            "preferred_categories": prefs.preferred_categories or [],
            "preferred_sources": prefs.preferred_sources or [],
            "preferred_languages": preferred_languages,
        }
        history_payload = [
            {
                "article_id": str(h.article_id),
                "category": h.article.category.name if h.article and h.article.category else None,
                "source_name": h.article.source.name if h.article and h.article.source else None,
                "keywords": _keywords_of(h.article) if h.article else None,
            }
            for h in history
        ]
        bookmark_payload = [
            {
                "article_id": str(b.article_id),
                "category": b.article.category.name if b.article and b.article.category else None,
                "source_name": b.article.source.name if b.article and b.article.source else None,
                "keywords": _keywords_of(b.article) if b.article else None,
            }
            for b in bookmarks
        ]

        scored = await self.recommender.process(
            {
                "article_embeddings": payload,
                "user_preferences": user_preferences,
                "reading_history": history_payload,
                "bookmarks": bookmark_payload,
            },
            limit=limit,
        )

        scored_by_id = {str(r["article_id"]): r for r in scored["recommendations"]}

        responses = []
        for article in articles:
            rank = scored_by_id.get(str(article.id))
            if not rank:
                continue
            responses.append(
                RecommendationResponse(
                    id=article.id,
                    title=article.title,
                    slug=article.slug,
                    summary=article.summary,
                    source_name=article.source.name if article.source else None,
                    category_name=article.category.name if article.category else None,
                    image_url=article.image_url,
                    published_at=article.published_at,
                    reason="; ".join(rank.get("reasons", [])) or None,
                    score=rank["score"],
                )
            )

        responses.sort(key=lambda r: r.score, reverse=True)
        return responses[:limit]
