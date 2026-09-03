"""Service-level tests for the recommendation service and cache read-through."""

from uuid import uuid4

from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.services.recommendation_service import (
    RecommendationService,
    invalidate_user_recommendations,
)
from app.utils.cache import cache_service


def build_service(db_session, **kwargs):
    return RecommendationService(
        article_repo=ArticleRepository(db_session),
        preference_repo=UserPreferenceRepository(db_session),
        reading_history_repo=ReadingHistoryRepository(db_session),
        bookmark_repo=BookmarkRepository(db_session),
        **kwargs,
    )


async def test_recommendations_exclude_read_and_bookmarked(
    db_session, article_fixture, regular_user
):
    await ReadingHistoryRepository(db_session).create(
        user_id=regular_user["id"], article_id=article_fixture["id"], read_duration_seconds=10
    )
    await db_session.commit()

    service = build_service(db_session)
    recs = await service.get_recommendations(regular_user["id"], limit=10, use_cache=False)
    assert recs == []


async def test_recommendations_prefer_preferred_category(db_session, article_fixture, regular_user):
    await UserPreferenceRepository(db_session).update(
        regular_user["id"],
        preferred_categories=["Technology"],
    )
    await db_session.commit()

    service = build_service(db_session)
    recs = await service.get_recommendations(regular_user["id"], limit=10, use_cache=False)
    assert len(recs) == 1
    assert recs[0].category_name == "Technology"


async def test_recommendations_cache_read_through(
    db_session, article_fixture, regular_user, monkeypatch
):
    calls = {"set": 0}
    service = build_service(db_session)

    async def fake_get(key):
        return None

    async def fake_set(key, value, ttl):
        calls["set"] += 1

    monkeypatch.setattr(cache_service, "initialize", lambda: _noop())
    monkeypatch.setattr(cache_service, "get", fake_get)
    monkeypatch.setattr(cache_service, "set", fake_set)

    recs = await service.get_recommendations(regular_user["id"], limit=10, use_cache=True)
    assert len(recs) == 1
    assert calls["set"] == 1


async def test_recommendations_served_from_cache(
    db_session, article_fixture, regular_user, monkeypatch
):
    await UserPreferenceRepository(db_session).update(
        regular_user["id"], preferred_categories=["Technology"]
    )
    await db_session.commit()

    service = build_service(db_session)
    fresh = await service.get_recommendations(regular_user["id"], limit=10, use_cache=False)
    assert len(fresh) == 1

    cached = [r.model_dump(mode="json") for r in fresh]
    monkeypatch.setattr(cache_service, "initialize", lambda: _noop())
    monkeypatch.setattr(cache_service, "get", lambda key: cached)
    monkeypatch.setattr(cache_service, "set", lambda key, value, ttl: _noop())

    service2 = build_service(db_session)
    recs = await service2.get_recommendations(regular_user["id"], limit=10, use_cache=True)
    assert len(recs) == 1
    assert recs[0].id == fresh[0].id


async def test_invalidate_user_recommendations(monkeypatch):
    deleted = []

    async def fake_initialize():
        return None

    async def fake_delete(key):
        deleted.append(key)

    monkeypatch.setattr(cache_service, "initialize", fake_initialize)
    monkeypatch.setattr(cache_service, "delete", fake_delete)

    await invalidate_user_recommendations(uuid4())
    assert len(deleted) == 1
    assert deleted[0].startswith("recommendations:user:")


async def test_invalidate_survives_redis_failure(monkeypatch):
    async def boom():
        raise ConnectionError("redis down")

    async def fake_initialize():
        return None

    monkeypatch.setattr(cache_service, "initialize", fake_initialize)
    monkeypatch.setattr(cache_service, "delete", boom)

    await invalidate_user_recommendations(uuid4())


async def _noop(*args, **kwargs):
    return None
