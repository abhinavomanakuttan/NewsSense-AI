"""Tests for the article ingestion service (HTTP fetch mocked)."""

import pytest

from app.services import article_ingestion_service as ais
from app.services.article_ingestion_service import ArticleIngestionService

RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://testfeed.com</link>
    <item>
      <title>Ingested Story</title>
      <link>https://testfeed.com/story-1</link>
      <description>Summary one.</description>
      <category>Tech</category>
      <category>AI</category>
    </item>
    <item>
      <title>Ingested Story Two</title>
      <link>https://testfeed.com/story-2</link>
      <description>Summary two.</description>
    </item>
  </channel>
</rss>
"""


@pytest.fixture
def mock_fetch(monkeypatch):
    async def fake_fetch(url: str) -> bytes:
        return RSS_XML

    monkeypatch.setattr(ais, "fetch_feed_content", fake_fetch)


@pytest.fixture
def service(db_session):
    return ArticleIngestionService(session=db_session)


async def test_ingest_source_creates_articles(db_session, source_fixture, service, mock_fetch):
    result = await service.ingest_source(source_fixture["id"])

    assert result["source"] == "Test News"
    assert result["fetched"] == 2
    assert result["new"] == 2
    assert result["duplicates"] == 0

    from sqlalchemy import select

    from app.models.article import Article

    rows = (await db_session.execute(select(Article))).scalars().all()
    assert len(rows) == 2
    assert {a.title for a in rows} == {"Ingested Story", "Ingested Story Two"}
    assert all(a.source_id is not None for a in rows)

    from app.models.source import Source

    source = (
        await db_session.execute(select(Source).where(Source.id == source_fixture["id"]))
    ).scalar()
    assert source.last_fetched_at is not None


async def test_ingest_deduplicates_same_feed(db_session, source_fixture, service, mock_fetch):
    first = await service.ingest_source(source_fixture["id"])
    assert first["new"] == 2

    second = await service.ingest_source(source_fixture["id"])
    assert second["new"] == 0
    assert second["duplicates"] == 2

    from sqlalchemy import func, select

    from app.models.article import Article

    count = (await db_session.execute(select(func.count()).select_from(Article))).scalar()
    assert count == 2


async def test_ingest_creates_tags_and_unique_slugs(
    db_session, source_fixture, service, mock_fetch
):
    await service.ingest_source(source_fixture["id"])

    from sqlalchemy import select

    from app.models.article import Article
    from app.models.tag import Tag

    tags = (await db_session.execute(select(Tag))).scalars().all()
    assert {t.name for t in tags} == {"Tech", "AI"}

    articles = (await db_session.execute(select(Article))).scalars().all()
    slugs = [a.slug for a in articles]
    assert len(slugs) == len(set(slugs))


async def test_ingest_inactive_source(db_session, source_fixture, service, mock_fetch):
    from sqlalchemy import update

    from app.models.source import Source

    await db_session.execute(
        update(Source).where(Source.id == source_fixture["id"]).values(is_active=False)
    )
    await db_session.commit()

    result = await service.ingest_source(source_fixture["id"])
    assert result["status"] == "skipped_inactive"


async def test_ingest_missing_source(service, mock_fetch):
    from uuid import uuid4

    from app.pipeline.feed_parser import FeedFetchError

    with pytest.raises(FeedFetchError):
        await service.ingest_source(uuid4())


async def test_ingest_preexisting_url_skipped(
    db_session, source_fixture, service, mock_fetch, article_fixture
):
    from sqlalchemy import update

    from app.models.article import Article

    await db_session.execute(
        update(Article)
        .where(Article.id == article_fixture["id"])
        .values(url="https://testfeed.com/story-1", content_hash="test-hash-1")
    )
    await db_session.commit()

    result = await service.ingest_source(source_fixture["id"])
    assert result["new"] == 1
    assert result["duplicates"] == 1
