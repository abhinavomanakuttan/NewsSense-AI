import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import ARTICLES_INGESTED_TOTAL
from app.db.session import async_session_factory
from app.models.article import Article
from app.models.source import Source
from app.pipeline.article_cleaner import (
    clean_html,
    clean_text,
    clean_url,
    generate_deduplication_fields,
    normalize_author,
    normalize_timestamp,
)
from app.pipeline.feed_parser import (
    FeedEntry,
    FeedFetchError,
    fetch_feed_content,
    parse_feed_content,
)
from app.pipeline.news_api_client import NewsApiClient
from app.pipeline.queue.redis_stream_producer import RedisStreamProducer
from app.repositories.article_repository import ArticleRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.tag_repository import TagRepository
from app.utils.text_utils import slugify

logger = logging.getLogger(__name__)


class ArticleIngestionService:
    """Coordinates fetching, cleaning, canonical normalization, persistence, and event queue streaming."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        article_repo: ArticleRepository | None = None,
        source_repo: SourceRepository | None = None,
        tag_repo: TagRepository | None = None,
        stream_producer: RedisStreamProducer | None = None,
    ):
        self._owns_session = session is None
        self.session = session or async_session_factory()
        self.article_repo = article_repo or ArticleRepository(self.session)
        self.source_repo = source_repo or SourceRepository(self.session)
        self.tag_repo = tag_repo or TagRepository(self.session)
        self.stream_producer = stream_producer or RedisStreamProducer()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.stream_producer:
            await self.stream_producer.close()
        if self._owns_session:
            await self.session.close()

    async def ingest_source(self, source_id: UUID) -> dict:
        """Fetch, normalize, persist, and publish articles for a single source with fault isolation."""
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise FeedFetchError(f"Source {source_id} not found")
        if not source.is_active:
            logger.info(f"Skipping inactive source {source.name}")
            return {"source": source.name, "status": "skipped_inactive"}

        try:
            if source.source_type == "api" or (source.api_endpoint and not source.feed_url):
                endpoint = source.api_endpoint or source.url
                client = NewsApiClient()
                entries = await client.fetch_news_api(
                    endpoint=endpoint,
                    category=source.category,
                    language=source.language or "en",
                    country=source.country,
                )
            else:
                feed_url = source.feed_url or source.url
                if not feed_url:
                    logger.info(f"Source {source.name} has no feed_url or api_endpoint configured")
                    return {"source": source.name, "status": "no_endpoint"}
                raw = await fetch_feed_content(feed_url)
                entries = parse_feed_content(raw, feed_url)

            result = await self.process_entries(source, entries)

            # Update success stats on Source
            source.last_fetched_at = _now_iso()
            source.last_fetch_success = True
            source.consecutive_failures = 0
            await self.session.flush()
            if self._owns_session:
                await self.session.commit()

            ARTICLES_INGESTED_TOTAL.inc(len(result.get("new_article_ids", [])))
            result["source"] = source.name
            return result

        except Exception as exc:
            # Fault isolation: log failure and update failure counts without stopping other pipeline operations
            logger.error(f"Failed to ingest source {source.name} ({source_id}): {exc}")
            source.last_fetched_at = _now_iso()
            source.last_fetch_success = False
            source.consecutive_failures = (source.consecutive_failures or 0) + 1
            await self.session.flush()
            if self._owns_session:
                await self.session.commit()
            return {
                "source": source.name,
                "status": "error",
                "error": str(exc),
                "consecutive_failures": source.consecutive_failures,
            }

    async def process_entries(self, source: Source, entries: list[FeedEntry]) -> dict:
        """Clean, normalize, generate deduplication preparation hashes, persist, and stream event."""
        seen_hashes: set[str] = set()
        new_count = 0
        duplicate_count = 0
        skipped_count = 0
        new_article_ids: list[str] = []

        for entry in entries:
            raw_title = entry.title.strip() if entry.title else ""
            if not raw_title:
                skipped_count += 1
                continue

            cleaned_content = clean_html(entry.content) if entry.content else clean_text(entry.summary)
            cleaned_summary = clean_text(entry.summary) if entry.summary else (cleaned_content[:300] if cleaned_content else None)
            cleaned_url = clean_url(entry.url or entry.guid)

            # Generate deduplication preparation hashes
            dedup_fields = generate_deduplication_fields(
                title=raw_title,
                content=cleaned_content,
                url=cleaned_url,
                source_domain=source.domain or source.url or "",
            )
            content_hash = dedup_fields["content_hash"]

            if content_hash in seen_hashes:
                duplicate_count += 1
                continue

            # DB-level dedupe: content_hash or url
            existing_by_hash = await self.article_repo.get_by_content_hash(content_hash)
            existing_by_url = await self.article_repo.get_by_url(cleaned_url) if cleaned_url else None
            if existing_by_hash or existing_by_url:
                seen_hashes.add(content_hash)
                duplicate_count += 1
                continue

            seen_hashes.add(content_hash)

            try:
                article = await self._create_canonical_article(
                    source=source,
                    entry=entry,
                    cleaned_content=cleaned_content,
                    cleaned_summary=cleaned_summary,
                    cleaned_url=cleaned_url,
                    dedup_fields=dedup_fields,
                )
                new_count += 1
                new_article_ids.append(str(article.id))

                # Publish event to Redis Streams queue
                article_dict = {
                    "article_id": str(article.id),
                    "source_id": str(source.id),
                    "source_name": source.name,
                    "category": source.category,
                    "title": article.title,
                    "url": article.url,
                    "normalized_title": article.normalized_title,
                    "content_hash": article.content_hash,
                    "url_hash": article.url_hash,
                    "source_hash": article.source_hash,
                    "article_fingerprint": article.article_fingerprint,
                    "published_at": article.published_at,
                    "language": article.language,
                    "country": article.country,
                }
                await self.stream_producer.publish_article_ingested(article_dict)

            except Exception as exc:
                logger.warning(f"Skipping entry '{raw_title}': {exc}")
                skipped_count += 1

        return {
            "fetched": len(entries),
            "new": new_count,
            "duplicates": duplicate_count,
            "skipped": skipped_count,
            "new_article_ids": new_article_ids,
        }

    async def _create_canonical_article(
        self,
        source: Source,
        entry: FeedEntry,
        cleaned_content: str,
        cleaned_summary: str | None,
        cleaned_url: str,
        dedup_fields: dict[str, str],
    ) -> Article:
        slug = await self._unique_slug(entry.title)
        url = cleaned_url or f"smartfeed://{dedup_fields['content_hash']}"
        author = normalize_author(entry.author)
        published_at = normalize_timestamp(entry.published_at)
        discovered_at = _now_iso()

        raw_meta = json.dumps(entry.to_dict(), default=str)

        article = await self.article_repo.create(
            title=entry.title.strip(),
            slug=slug,
            url=url,
            source_id=source.id,
            source_name=source.name,
            category_name=source.category,
            content=cleaned_content,
            summary=cleaned_summary,
            author=author,
            published_at=published_at,
            discovered_at=discovered_at,
            image_url=entry.image_url,
            content_hash=dedup_fields["content_hash"],
            normalized_title=dedup_fields["normalized_title"],
            url_hash=dedup_fields["url_hash"],
            source_hash=dedup_fields["source_hash"],
            article_fingerprint=dedup_fields["article_fingerprint"],
            language=source.language or "en",
            country=source.country,
            raw_metadata=raw_meta,
        )

        if entry.tags:
            await self.session.refresh(article, attribute_names=["tags"])
            for tag_name in entry.tags[:10]:
                tag_slug = slugify(tag_name)
                if not tag_slug:
                    continue
                tag = await self.tag_repo.get_or_create(tag_name, tag_slug)
                article.tags.append(tag)

        return article

    async def _unique_slug(self, title: str) -> str:
        base = slugify(title)[:450]
        if not base:
            base = "article"
        candidate = base
        suffix = 2
        while True:
            existing = await self.article_repo.get_by_slug(candidate)
            if not existing:
                return candidate
            candidate = f"{base[:445]}-{suffix}"
            suffix += 1


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()

