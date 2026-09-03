"""API tests for admin pipeline triggers (feed refresh / full ingest)."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.services import article_ingestion_service as ais
from tests.conftest import TEST_DATABASE_URL
from tests.pipeline.test_ingestion import RSS_XML


async def test_admin_refresh_source_ingests_inline(
    client, admin_headers, source_fixture, monkeypatch
):
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
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "refreshed inline" in body["message"]
    assert "'new': 2" in body["message"]


async def test_admin_refresh_denied_for_user(client, auth_headers, source_fixture):
    resp = await client.post(
        f"/api/v1/admin/sources/{source_fixture['id']}/refresh", headers=auth_headers
    )
    assert resp.status_code == 403


async def test_admin_refresh_missing_source(client, admin_headers):
    resp = await client.post(
        "/api/v1/admin/sources/00000000-0000-0000-0000-000000000000/refresh", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "not found" in resp.json()["message"]
