"""Redis Stream Producer for real-time article event streaming.

Publishes normalized Article events to Redis Stream `stream:news:ingested`
for downstream processing by the Deduplication, Clustering, and NLP Agents.
Handles errors with Dead Letter Queue fallback (`stream:news:dlq`).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

STREAM_NEWS_INGESTED = "stream:news:ingested"
STREAM_NEWS_DLQ = "stream:news:dlq"
MAX_STREAM_LENGTH = 10000


class RedisStreamProducer:
    """Producer for publishing article events to Redis Streams."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def publish_article_ingested(self, article_data: dict) -> str | None:
        """Publish normalized Article event payload to Redis Stream `stream:news:ingested`.

        Returns stream message ID or None on failure.
        """
        try:
            client = await self._get_client()

            event_id = str(uuid4())
            timestamp = datetime.now(UTC).isoformat()

            payload = {
                "event_id": event_id,
                "event_type": "article_ingested",
                "timestamp": timestamp,
                "article_id": str(article_data.get("article_id") or article_data.get("id") or ""),
                "source_id": str(article_data.get("source_id") or ""),
                "source_name": article_data.get("source_name") or "",
                "category": article_data.get("category") or article_data.get("category_name") or "",
                "title": article_data.get("title") or "",
                "url": article_data.get("url") or "",
                "normalized_title": article_data.get("normalized_title") or "",
                "content_hash": article_data.get("content_hash") or "",
                "url_hash": article_data.get("url_hash") or "",
                "source_hash": article_data.get("source_hash") or "",
                "article_fingerprint": article_data.get("article_fingerprint") or "",
                "published_at": article_data.get("published_at") or "",
                "language": article_data.get("language") or "en",
                "country": article_data.get("country") or "",
            }

            # Redis Streams stores string field-value pairs
            stream_entry = {
                "event_id": event_id,
                "event_type": "article_ingested",
                "data": json.dumps(payload),
            }

            message_id = await client.xadd(
                STREAM_NEWS_INGESTED,
                fields=stream_entry,
                maxlen=MAX_STREAM_LENGTH,
                approximate=True,
            )
            logger.debug(f"Published article {payload['article_id']} to {STREAM_NEWS_INGESTED} (msg_id={message_id})")
            return message_id

        except Exception as exc:
            logger.error(f"Failed to publish article event to Redis Stream: {exc}")
            await self.publish_to_dlq(article_data, error=str(exc))
            return None

    async def publish_to_dlq(self, payload: dict, error: str) -> str | None:
        """Publish failed events to Dead Letter Queue stream (`stream:news:dlq`)."""
        try:
            client = await self._get_client()
            dlq_entry = {
                "failed_at": datetime.now(UTC).isoformat(),
                "error": error,
                "payload": json.dumps(payload, default=str),
            }
            message_id = await client.xadd(STREAM_NEWS_DLQ, fields=dlq_entry, maxlen=MAX_STREAM_LENGTH)
            logger.warning(f"Routed failed ingestion payload to DLQ {STREAM_NEWS_DLQ} (msg_id={message_id})")
            return message_id
        except Exception as dlq_exc:
            logger.critical(f"Critical failure writing to DLQ: {dlq_exc}")
            return None

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
