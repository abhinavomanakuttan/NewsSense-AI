"""API edge-case tests: 404/409 branches and admin pipeline fallbacks."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.repositories.event_repository import EventRepository
from app.repositories.source_repository import SourceRepository
from app.services import article_ingestion_service as ais
from tests.conftest import TEST_DATABASE_URL
from tests.pipeline.test_ingestion import RSS_XML

SOURCE_PAYLOAD = {
    "name": "Second Source",
    "url": "https://second.example",
    "feed_url": "https://second.example/rss",
    "source_type": "rss",
    "language": "en",
}


async def test_list_tags_empty(client):
    resp = await client.get("/api/v1/tags")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_and_duplicate_tag(client):
    created = await client.post("/api/v1/tags", json={"name": "AI", "slug": "ai"})
    assert created.status_code == 201
    assert created.json()["slug"] == "ai"

    duplicate = await client.post("/api/v1/tags", json={"name": "AI", "slug": "ai"})
    assert duplicate.status_code == 409


async def test_create_source_success(client, auth_headers):
    resp = await client.post("/api/v1/sources", json=SOURCE_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Second Source"


async def test_create_duplicate_source(client, auth_headers, source_fixture):
    resp = await client.post(
        "/api/v1/sources",
        json={**SOURCE_PAYLOAD, "url": source_fixture["name"] and "https://testnews.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


async def test_update_source_not_found(client, auth_headers):
    resp = await client.put(
        f"/api/v1/sources/{uuid4()}",
        json={"name": "Nope"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_delete_source_not_found(client, auth_headers):
    resp = await client.delete(f"/api/v1/sources/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


async def test_update_source_success(client, auth_headers, source_fixture):
    resp = await client.put(
        f"/api/v1/sources/{source_fixture['id']}",
        json={"name": "Renamed News"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed News"


async def test_event_not_found(client):
    resp = await client.get("/api/v1/events/nonexistent-event")
    assert resp.status_code == 404


async def test_event_get_and_articles(client, db_session, article_fixture):
    repo = EventRepository(db_session)
    event = await repo.create(
        title="Big Event",
        slug="big-event",
        importance_score=0.9,
        is_active=True,
    )
    await db_session.flush()

    found = await client.get("/api/v1/events/big-event")
    assert found.status_code == 200
    assert found.json()["slug"] == "big-event"

    listed = await client.get("/api/v1/events")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == str(event.id)

    articles = await client.get(f"/api/v1/events/{event.id}/articles")
    assert articles.status_code == 200


async def test_admin_refresh_inactive_source(client, admin_headers, db_session, source_fixture):
    repo = SourceRepository(db_session)
    await repo.update(source_fixture["id"], is_active=False)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/admin/sources/{source_fixture['id']}/refresh", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "inactive or has no feed_url" in resp.json()["message"]


async def test_admin_refresh_queued_when_broker_available(
    client, admin_headers, source_fixture, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.celery_broker_url", "memory://test")
    queued = []

    class FakeTask:
        @staticmethod
        def delay(source_id):
            queued.append(source_id)

    monkeypatch.setattr("app.api.v1.admin.fetch_source", FakeTask)

    resp = await client.post(
        f"/api/v1/admin/sources/{source_fixture['id']}/refresh", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "refresh queued" in resp.json()["message"]
    assert queued == [str(source_fixture["id"])]


async def test_admin_refresh_inline_fallback_when_delay_fails(
    client, admin_headers, source_fixture, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.celery_broker_url", "memory://test")

    class RaisingTask:
        @staticmethod
        def delay(source_id):
            raise RuntimeError("broker exploded")

    monkeypatch.setattr("app.api.v1.admin.fetch_source", RaisingTask)

    async def fake_fetch(url: str) -> bytes:
        return RSS_XML

    monkeypatch.setattr(ais, "fetch_feed_content", fake_fetch)
    monkeypatch.setattr(
        ais,
        "async_session_factory",
        async_sessionmaker(
            create_async_engine(TEST_DATABASE_URL, poolclass=NullPool),
            class_=AsyncSession,
            expire_on_commit=False,
        ),
    )

    resp = await client.post(
        f"/api/v1/admin/sources/{source_fixture['id']}/refresh", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "refreshed inline" in resp.json()["message"]


async def test_admin_ingest_all_queued(client, admin_headers, source_fixture, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.celery_broker_url", "memory://test")

    dispatched = []

    class FakeTask:
        @staticmethod
        def delay():
            dispatched.append(True)

    monkeypatch.setattr("app.pipeline.tasks.feed_fetcher.fetch_all_feeds", FakeTask)

    resp = await client.post("/api/v1/admin/ingest-all", headers=admin_headers)
    assert resp.status_code == 200
    assert "Full ingestion queued" in resp.json()["message"]
    assert dispatched == [True]


async def test_admin_ingest_all_inline(
    client, admin_headers, source_fixture, db_session, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.enable_enrichment", False)

    async def fake_fetch(url: str) -> bytes:
        return RSS_XML

    monkeypatch.setattr(ais, "fetch_feed_content", fake_fetch)
    monkeypatch.setattr(
        ais,
        "async_session_factory",
        async_sessionmaker(
            create_async_engine(TEST_DATABASE_URL, poolclass=NullPool),
            class_=AsyncSession,
            expire_on_commit=False,
        ),
    )

    # Force the inline path: no broker, no feed URL qualification issue.
    await SourceRepository(db_session).update(
        source_fixture["id"], feed_url="https://testnews.com/rss", is_active=True
    )
    await db_session.flush()

    resp = await client.post("/api/v1/admin/ingest-all", headers=admin_headers)
    assert resp.status_code == 200
    assert "Inline ingestion finished" in resp.json()["message"]
