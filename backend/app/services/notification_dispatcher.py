"""Real-time notification dispatch.

Pushes a notification to the connected sockets in this process and publishes
it to a Redis pub/sub channel so every other API worker delivers it to its own
local sockets too. Degrades gracefully: when Redis is unreachable the message
is still delivered locally (single-process dev mode), and a dead subscriber
simply stops without breaking the request path.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any

from app.core.config import settings
from app.core.metrics import NOTIFICATIONS_DISPATCHED_TOTAL
from app.services.ws_manager import connection_manager

logger = logging.getLogger(__name__)

CHANNEL = "smartfeed:notifications"


class NotificationDispatcher:
    def __init__(self, manager=connection_manager):
        self.manager = manager
        self._pubsub_client: Any | None = None
        self._subscriber_task: asyncio.Task | None = None

    async def publish(self, user_id: str, payload: dict[str, Any]) -> None:
        """Deliver locally and fan out to other workers via Redis."""
        message = {
            "type": "notification",
            "user_id": str(user_id),
            "notification": payload,
        }
        await self.manager.send_to_user(str(user_id), message)
        with suppress(Exception):
            NOTIFICATIONS_DISPATCHED_TOTAL.inc()
            await self._redis_publish(message)

    async def _redis_publish(self, message: dict[str, Any]) -> None:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await client.publish(CHANNEL, json.dumps(message))
            await client.aclose()
        except Exception as exc:
            logger.debug(f"Redis publish skipped: {exc}")

    async def start(self) -> None:
        if self._subscriber_task is not None:
            return
        try:
            import redis.asyncio as aioredis

            self._pubsub_client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._pubsub_client.ping()
        except Exception as exc:
            logger.warning(f"Notification subscriber disabled (Redis unavailable): {exc}")
            self._pubsub_client = None
            return
        self._subscriber_task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        pubsub = self._pubsub_client.pubsub()
        try:
            await pubsub.subscribe(CHANNEL)
            logger.info(f"Notification subscriber listening on '{CHANNEL}'")
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    user_id = str(data.get("user_id", ""))
                    if user_id:
                        await self.manager.send_to_user(
                            user_id,
                            {
                                "type": "notification",
                                "notification": data.get("notification", {}),
                            },
                        )
                except Exception as exc:
                    logger.warning(f"Failed to route notification: {exc}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Notification subscriber stopped: {exc}")
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe(CHANNEL)

    async def stop(self) -> None:
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._subscriber_task
            self._subscriber_task = None
        if self._pubsub_client is not None:
            with suppress(Exception):
                await self._pubsub_client.aclose()
            self._pubsub_client = None


notification_dispatcher = NotificationDispatcher()
