"""Tests for recommender scoring, trending task, and vector store."""

import pytest
from sqlalchemy import update

from app.ai.recommender import ArticleRecommender
from app.models.article import Article
from app.repositories.article_repository import ArticleRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.services.recommendation_service import RecommendationService
from app.services.vector_store_service import VectorStoreService


@pytest.fixture
def recommender():
    return ArticleRecommender()


async def test_recommender_scores_by_preferences(recommender):
    result = await recommender.process(
        {
            "article_embeddings": [
                {
                    "id": "a1",
                    "category": "technology",
                    "credibility_score": 0.9,
                    "view_count": "500",
                },
                {"id": "a2", "category": "sports", "credibility_score": 0.5, "view_count": "0"},
            ],
            "user_preferences": {"preferred_categories": ["technology"], "preferred_sources": []},
            "reading_history": [],
        },
        limit=10,
    )
    recs = result["recommendations"]
    assert recs[0]["article_id"] == "a1"
    assert recs[0]["score"] > recs[1]["score"]
    assert "interest in technology" in recs[0]["reasons"]


async def test_recommender_skips_read_articles(recommender):
    result = await recommender.process(
        {
            "article_embeddings": [{"id": "a1", "category": "technology"}],
            "user_preferences": {},
            "reading_history": [{"article_id": "a1"}],
        },
        limit=10,
    )
    assert result["recommendations"] == []


async def test_recommender_boosts_read_categories(recommender):
    result = await recommender.process(
        {
            "article_embeddings": [
                {"id": "a1", "category": "technology", "credibility_score": 0.5},
                {"id": "a2", "category": "sports", "credibility_score": 0.5},
            ],
            "user_preferences": {},
            "reading_history": [
                {"article_id": "old1", "category": "technology"},
                {"article_id": "old2", "category": "technology"},
            ],
        },
        limit=10,
    )
    recs = {r["article_id"]: r for r in result["recommendations"]}
    assert recs["a1"]["score"] > recs["a2"]["score"]
    assert any("you read" in r for r in recs["a1"]["reasons"])


async def test_recommender_boosts_keyword_overlap(recommender):
    result = await recommender.process(
        {
            "article_embeddings": [
                {"id": "a1", "category": "tech", "keywords": '["ai", "health"]'},
                {"id": "a2", "category": "tech", "keywords": '["sports", "football"]'},
            ],
            "user_preferences": {},
            "reading_history": [{"article_id": "old1", "keywords": '["ai"]'}],
        },
        limit=10,
    )
    recs = {r["article_id"]: r for r in result["recommendations"]}
    assert recs["a1"]["score"] > recs["a2"]["score"]
    assert any("matches topics" in r for r in recs["a1"]["reasons"])


async def test_recommender_excludes_non_preferred_language(recommender):
    result = await recommender.process(
        {
            "article_embeddings": [
                {"id": "a1", "language": "en", "category": "technology"},
                {"id": "a2", "language": "fr", "category": "technology"},
            ],
            "user_preferences": {"preferred_languages": ["en"]},
            "reading_history": [],
        },
        limit=10,
    )
    ids = [r["article_id"] for r in result["recommendations"]]
    assert ids == ["a1"]


async def test_recommender_skips_bookmarked_articles(recommender):
    result = await recommender.process(
        {
            "article_embeddings": [{"id": "a1", "category": "technology"}],
            "user_preferences": {},
            "reading_history": [],
            "bookmarks": [{"article_id": "a1"}],
        },
        limit=10,
    )
    assert result["recommendations"] == []


async def test_recommender_recency_bonus(recommender):
    from datetime import date

    today = date.today().isoformat()
    old = "2020-01-01T00:00:00"
    result = await recommender.process(
        {
            "article_embeddings": [
                {"id": "fresh", "category": "tech", "published_at": today},
                {"id": "old", "category": "tech", "published_at": old},
            ],
            "user_preferences": {},
            "reading_history": [],
        },
        limit=10,
    )
    recs = {r["article_id"]: r for r in result["recommendations"]}
    assert recs["fresh"]["score"] > recs["old"]["score"]


async def test_recommender_respects_limit(recommender):
    result = await recommender.process(
        {
            "article_embeddings": [{"id": f"a{i}", "category": "technology"} for i in range(10)],
            "user_preferences": {},
            "reading_history": [],
        },
        limit=3,
    )
    assert len(result["recommendations"]) == 3


async def test_update_trending_task(db_session, article_fixture, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from tests.conftest import TEST_DATABASE_URL

    await db_session.execute(
        update(Article).where(Article.id == article_fixture["id"]).values(view_count="1500")
    )
    await db_session.commit()

    import app.pipeline.tasks.recommendation_updater as ru

    monkeypatch.setattr(
        ru,
        "async_session_factory",
        async_sessionmaker(
            create_async_engine(TEST_DATABASE_URL, poolclass=NullPool),
            class_=AsyncSession,
            expire_on_commit=False,
        ),
    )
    monkeypatch.setattr(ru.cache_service, "initialize", _noop)
    monkeypatch.setattr(ru.cache_service, "set", _noop)

    result = await ru._update_trending()
    assert result["status"] == "trending_updated"
    assert result["count"] >= 1


async def _noop(*args, **kwargs):
    return None


async def test_vector_store_unavailable_noop():
    store = VectorStoreService(host="127.0.0.1", port=1)
    store._available = False
    assert store.is_available() is False
    assert store.upsert("x", [0.1]) is None
    assert store.search([0.1]) == []
    assert store.remove("x") is False


async def test_recommendation_service_with_recommender(db_session, article_fixture, regular_user):
    service = RecommendationService(
        article_repo=ArticleRepository(db_session),
        preference_repo=UserPreferenceRepository(db_session),
        reading_history_repo=ReadingHistoryRepository(db_session),
    )
    recs = await service.get_recommendations(regular_user["id"], limit=10)
    assert isinstance(recs, list)
