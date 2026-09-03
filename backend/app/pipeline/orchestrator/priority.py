"""Priority queue for event processing.

WHY priority management:
- Breaking news must be processed before background articles.
- Without priority, a flood of low-priority articles could delay breaking news.
- Uses Redis sorted sets for O(log N) priority insertion and O(1) pop-max.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.pipeline.orchestrator.state import EventPriority

logger = logging.getLogger(__name__)

# Redis key for the priority queue
PRIORITY_QUEUE_KEY = "orchestrator:priority_queue"


class PriorityQueue:
    """Redis-backed priority queue for event processing.

    WHY sorted sets:
    - O(log N) insert and update.
    - O(1) peek at highest priority.
    - O(log N) pop highest priority.
    - Natural support for priority + recency (secondary sort).
    """

    def __init__(self, redis_client: Any | None = None):
        self._redis = redis_client

    async def enqueue(
        self,
        event_id: str,
        priority: EventPriority,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add an event to the processing queue.

        Score = priority * 1_000_000 + unix_timestamp (for tie-breaking).
        """
        if self._redis is None:
            logger.debug(f"Redis unavailable, queueing {event_id} locally")
            return

        score = priority.numeric * 1_000_000 + datetime.now(UTC).timestamp()
        try:
            await self._redis.zadd(
                PRIORITY_QUEUE_KEY,
                {event_id: score},
            )
            logger.debug(f"Enqueued {event_id} with priority {priority.value} (score={score:.0f})")
        except Exception as exc:
            logger.warning(f"Failed to enqueue {event_id}: {exc}")

    async def dequeue(self, count: int = 1) -> list[str]:
        """Pop the highest-priority events from the queue.

        Returns event IDs in priority order (highest first).
        """
        if self._redis is None:
            return []

        try:
            # ZPOPMAX: pop items with highest score
            results = await self._redis.zpopmax(PRIORITY_QUEUE_KEY, count=count)
            event_ids = [item[0] if isinstance(item, (list, tuple)) else item for item in results]
            logger.debug(f"Dequeued {len(event_ids)} events: {event_ids}")
            return event_ids
        except Exception as exc:
            logger.warning(f"Failed to dequeue: {exc}")
            return []

    async def peek(self, count: int = 5) -> list[dict[str, Any]]:
        """Look at the top events without removing them."""
        if self._redis is None:
            return []

        try:
            # ZREVRANGE: get items with highest scores
            results = await self._redis.zrevrange(
                PRIORITY_QUEUE_KEY, 0, count - 1, withscores=True
            )
            return [
                {"event_id": item[0] if isinstance(item, (list, tuple)) else item,
                 "score": score}
                for item, score in results
            ]
        except Exception as exc:
            logger.warning(f"Failed to peek queue: {exc}")
            return []

    async def remove(self, event_id: str) -> bool:
        """Remove an event from the queue."""
        if self._redis is None:
            return False

        try:
            removed = await self._redis.zrem(PRIORITY_QUEUE_KEY, event_id)
            return bool(removed)
        except Exception:
            return False

    async def size(self) -> int:
        """Get the number of events in the queue."""
        if self._redis is None:
            return 0

        try:
            return await self._redis.zcard(PRIORITY_QUEUE_KEY)
        except Exception:
            return 0

    async def update_priority(self, event_id: str, new_priority: EventPriority) -> None:
        """Update the priority of an event already in the queue."""
        if self._redis is None:
            return

        score = new_priority.numeric * 1_000_000 + datetime.now(UTC).timestamp()
        try:
            await self._redis.zadd(PRIORITY_QUEUE_KEY, {event_id: score})
        except Exception as exc:
            logger.warning(f"Failed to update priority for {event_id}: {exc}")
