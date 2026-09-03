from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.repositories.search_history_repository import SearchHistoryRepository


async def test_analytics_denied_for_regular_user(client, auth_headers):
    for endpoint in [
        "/api/v1/analytics/activity",
        "/api/v1/analytics/articles-trend",
        "/api/v1/analytics/categories",
        "/api/v1/analytics/sources",
        "/api/v1/analytics/sentiment",
        "/api/v1/analytics/events",
    ]:
        resp = await client.get(endpoint, headers=auth_headers)
        assert resp.status_code == 403, endpoint


async def test_activity_returns_zero_filled_series(client, admin_headers):
    resp = await client.get("/api/v1/analytics/activity?days=7", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 7
    for day in body:
        assert day["active_users"] == 0
        assert day["page_views"] == 0
        assert day["searches"] == 0
        assert day["bookmarks"] == 0


async def test_activity_counts_user_actions(
    client, admin_headers, regular_user, article_fixture, db_session
):
    await ReadingHistoryRepository(db_session).create(
        user_id=regular_user["id"], article_id=article_fixture["id"]
    )
    await SearchHistoryRepository(db_session).create(user_id=regular_user["id"], query="AI")
    await BookmarkRepository(db_session).create(
        user_id=regular_user["id"], article_id=article_fixture["id"]
    )
    await db_session.flush()

    resp = await client.get("/api/v1/analytics/activity?days=7", headers=admin_headers)
    assert resp.status_code == 200
    today = resp.json()[-1]
    assert today["active_users"] == 1
    assert today["page_views"] == 1
    assert today["searches"] == 1
    assert today["bookmarks"] == 1


async def test_categories_and_sources_reflect_articles(
    client, admin_headers, article_fixture, source_fixture
):
    cats = (await client.get("/api/v1/analytics/categories", headers=admin_headers)).json()
    assert any(c["category"] == "Technology" and c["article_count"] >= 1 for c in cats)

    sources = (await client.get("/api/v1/analytics/sources", headers=admin_headers)).json()
    assert any(s["source"] == source_fixture["name"] and s["article_count"] >= 1 for s in sources)


async def test_sentiment_distribution(client, admin_headers, article_fixture, db_session):
    from sqlalchemy import update

    from app.models.article import Article

    await db_session.execute(
        update(Article).where(Article.id == article_fixture["id"]).values(sentiment="positive")
    )
    await db_session.flush()

    resp = await client.get("/api/v1/analytics/sentiment", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert any(item["sentiment"] == "positive" and item["count"] >= 1 for item in body)


async def test_articles_trend_counts_today(client, admin_headers, article_fixture):
    resp = await client.get("/api/v1/analytics/articles-trend?days=7", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 7
    assert body[-1]["count"] >= 1


async def test_track_event_and_list(client, admin_headers, auth_headers):
    tracked = await client.post(
        "/api/v1/analytics/track",
        json={
            "event_type": "page_view",
            "value": 1,
            "metadata": {"path": "/feed"},
        },
        headers=auth_headers,
    )
    assert tracked.status_code == 200
    event = tracked.json()
    assert event["event_type"] == "page_view"
    assert event["metadata"]["path"] == "/feed"
    assert event["user_id"]

    listed = await client.get("/api/v1/analytics/events", headers=admin_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert body["events"][0]["id"] == event["id"]


async def test_track_event_allows_anonymous(client, admin_headers):
    tracked = await client.post(
        "/api/v1/analytics/track",
        json={"event_type": "page_view"},
    )
    assert tracked.status_code == 200
    assert tracked.json()["user_id"] is None

    listed = await client.get("/api/v1/analytics/events", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


async def test_events_pagination(client, admin_headers):
    listed = await client.get("/api/v1/analytics/events?limit=1&skip=0", headers=admin_headers)
    assert listed.status_code == 200
    assert len(listed.json()["events"]) <= 1


async def test_record_event_helper(db_session, regular_user, article_fixture):
    repo = AnalyticsRepository(db_session)
    event = await repo.record_event(
        event_type="click",
        user_id=str(regular_user["id"]),
        article_id=str(article_fixture["id"]),
        metadata={"widget": "card"},
    )
    assert event.event_type == "click"
    assert event.user_id == str(regular_user["id"])
    assert event.event_metadata == {"widget": "card"}
