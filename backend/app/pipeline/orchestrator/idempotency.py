"""Idempotency guarantees for event processing.

WHY idempotency:
- The same article may arrive multiple times from different sources or retries.
- Without idempotency, an event could be summarised 10 times.
- We use Redis-based distributed locks with TTL to prevent concurrent processing.
- A processing_version tracks the logical version of the event state.

Two levels of deduplication:
1. Event-level: prevents concurrent processing of the same event.
2. Article-level: prevents processing the same article twice (content hash).

Both use Redis with graceful degradation when Redis is unavailable.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class IdempotencyGuard:
    """Distributed lock to prevent duplicate processing of the same event.

    WHY Redis-based:
    - Multiple Celery workers may receive the same task.
    - Redis SETNX provides atomic lock acquisition.
    - TTL ensures locks are released even if the worker crashes.
    """

    def __init__(self, redis_client: Any | None = None):
        self._redis = redis_client

    async def acquire(self, event_id: str, agent_name: str, ttl_seconds: int = 300) -> bool:
        """Try to acquire a processing lock for an event+agent pair.

        Returns True if lock acquired, False if another worker is already processing.
        """
        if self._redis is None:
            # No Redis available — allow processing (degraded mode)
            return True

        lock_key = f"orchestrator:lock:{event_id}:{agent_name}"
        try:
            acquired = await self._redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
            if acquired:
                logger.debug(f"Acquired lock for {event_id}:{agent_name}")
            else:
                logger.info(f"Lock already held for {event_id}:{agent_name}, skipping")
            return bool(acquired)
        except Exception as exc:
            logger.warning(f"Failed to acquire lock for {event_id}:{agent_name}: {exc}")
            # On Redis failure, allow processing (degraded mode)
            return True

    async def release(self, event_id: str, agent_name: str) -> None:
        """Release the processing lock."""
        if self._redis is None:
            return

        lock_key = f"orchestrator:lock:{event_id}:{agent_name}"
        try:
            await self._redis.delete(lock_key)
            logger.debug(f"Released lock for {event_id}:{agent_name}")
        except Exception as exc:
            logger.warning(f"Failed to release lock for {event_id}:{agent_name}: {exc}")

    async def is_processing(self, event_id: str, agent_name: str) -> bool:
        """Check if an event+agent pair is currently being processed."""
        if self._redis is None:
            return False

        lock_key = f"orchestrator:lock:{event_id}:{agent_name}"
        try:
            exists = await self._redis.exists(lock_key)
            return bool(exists)
        except Exception:
            return False


class DeduplicationChecker:
    """Check if an article has already been processed by the pipeline.

    WHY article-level dedup:
    - Content hash matching prevents processing the same article twice.
    - Article ID matching prevents processing articles already in the system.
    - Processing version prevents re-running completed stages.
    """

    def __init__(self, redis_client: Any | None = None):
        self._redis = redis_client

    async def is_article_processed(self, article_id: str) -> bool:
        """Check if an article has already been fully processed."""
        if self._redis is None:
            return False

        key = f"orchestrator:processed:{article_id}"
        try:
            return bool(await self._redis.exists(key))
        except Exception:
            return False

    async def mark_article_processed(self, article_id: str, ttl_seconds: int = 86400) -> None:
        """Mark an article as fully processed (24h TTL by default)."""
        if self._redis is None:
            return

        key = f"orchestrator:processed:{article_id}"
        try:
            await self._redis.set(key, "1", ex=ttl_seconds)
        except Exception as exc:
            logger.warning(f"Failed to mark article {article_id} as processed: {exc}")

    async def get_processing_version(self, event_id: str) -> int:
        """Get the current processing version for an event."""
        if self._redis is None:
            return 1

        key = f"orchestrator:version:{event_id}"
        try:
            version = await self._redis.get(key)
            return int(version) if version else 1
        except Exception:
            return 1

    async def increment_processing_version(self, event_id: str) -> int:
        """Increment the processing version (used when reprocessing)."""
        if self._redis is None:
            return 1

        key = f"orchestrator:version:{event_id}"
        try:
            new_version = await self._redis.incr(key)
            return int(new_version)
        except Exception:
            return 1

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute a content hash for deduplication.

        WHY content hash:
        - Same article from different sources has the same content.
        - Hash-based dedup is O(1) lookup vs O(N) text comparison.
        - SHA-256 provides collision-resistant hashing.
        """
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

    async def is_content_duplicate(
        self,
        content_hash: str,
        event_id: str | None = None,
        ttl_seconds: int = 86400,
    ) -> bool:
        """Check if content with this hash has been seen before.

        WHY content-level dedup:
        - Same story published by multiple outlets has near-identical content.
        - Prevents clustering the same story as separate events.
        - Uses a separate key namespace from article-level dedup.
        """
        if self._redis is None:
            return False

        key = f"orchestrator:content_hash:{content_hash}"
        try:
            return bool(await self._redis.exists(key))
        except Exception:
            return False

    async def mark_content_seen(
        self,
        content_hash: str,
        event_id: str,
        ttl_seconds: int = 86400,
    ) -> None:
        """Record that content with this hash belongs to this event."""
        if self._redis is None:
            return

        key = f"orchestrator:content_hash:{content_hash}"
        try:
            await self._redis.set(key, event_id, ex=ttl_seconds)
        except Exception as exc:
            logger.warning(f"Failed to mark content hash {content_hash}: {exc}")

    async def get_event_for_content(self, content_hash: str) -> str | None:
        """Look up which event a content hash belongs to.

        WHY:
        - When a new article arrives, check if its content matches an existing event.
        - Enables attaching new articles to existing events instead of creating new ones.
        """
        if self._redis is None:
            return None

        key = f"orchestrator:content_hash:{content_hash}"
        try:
            event_id = await self._redis.get(key)
            return event_id if event_id else None
        except Exception:
            return None
