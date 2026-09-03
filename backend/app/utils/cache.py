import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings


class CacheService:
    def __init__(self):
        self.client: aioredis.Redis | None = None

    async def initialize(self):
        if self.client is None:
            self.client = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        if not self.client:
            return None
        value = await self.client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self.client:
            return
        await self.client.setex(key, ttl, json.dumps(value))

    async def delete(self, key: str) -> None:
        if not self.client:
            return
        await self.client.delete(key)

    async def invalidate_pattern(self, pattern: str) -> None:
        if not self.client:
            return
        cursor = 0
        while True:
            cursor, keys = await self.client.scan(cursor, match=pattern)
            if keys:
                await self.client.delete(*keys)
            if cursor == 0:
                break

    async def close(self):
        if self.client:
            await self.client.close()


cache_service = CacheService()
