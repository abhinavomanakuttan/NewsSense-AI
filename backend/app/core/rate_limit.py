import time
from collections import defaultdict
from collections.abc import Callable

from .config import settings
from .exceptions import RateLimitError


class InMemoryRateLimiter:
    def __init__(self):
        self.requests: dict = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, period: int) -> bool:
        now = time.time()
        window_start = now - period

        self.requests[key] = [t for t in self.requests[key] if t > window_start]

        if len(self.requests[key]) >= max_requests:
            return False

        self.requests[key].append(now)
        return True


rate_limiter = InMemoryRateLimiter()


class RateLimitMiddleware:
    """Pure ASGI rate limiter for HTTP requests.

    WebSocket scopes pass through untouched (HTTP middleware cannot wrap a
    websocket handshake).
    """

    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        key = f"{client_ip}:{scope['path']}"

        if not rate_limiter.is_allowed(
            key,
            settings.rate_limit_requests,
            settings.rate_limit_period_seconds,
        ):
            raise RateLimitError()

        await self.app(scope, receive, send)
