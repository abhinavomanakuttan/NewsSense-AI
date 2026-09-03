"""Tests for NotificationDispatcher: local delivery, Redis fan-out, subscriber."""

import asyncio
import json

import pytest
import redis.asyncio as aioredis

from app.services.notification_dispatcher import NotificationDispatcher


class FakeManager:
    def __init__(self):
        self.sent: list[tuple[str, dict]] = []
        self._available = False

    async def send_to_user(self, user_id: str, payload: dict) -> bool:
        self.sent.append((user_id, payload))
        return True


@pytest.mark.asyncio
async def test_publish_delivers_locally(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    async def noop_redis(message):
        pass

    monkeypatch.setattr(dispatcher, "_redis_publish", noop_redis)

    await dispatcher.publish("user-1", {"id": "n1", "title": "Hello"})

    assert len(manager.sent) == 1
    user_id, payload = manager.sent[0]
    assert user_id == "user-1"
    assert payload["type"] == "notification"
    assert payload["notification"] == {"id": "n1", "title": "Hello"}


@pytest.mark.asyncio
async def test_redis_publish_failure_does_not_raise(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    async def failing_redis(message):
        raise RuntimeError("redis down")

    monkeypatch.setattr(dispatcher, "_redis_publish", failing_redis)

    # Must not raise even though the Redis side fails.
    await dispatcher.publish("user-1", {"id": "n1", "title": "Hello"})
    assert len(manager.sent) == 1


@pytest.mark.asyncio
async def test_start_disabled_when_redis_unavailable(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    async def failing_ping(self):
        raise OSError("connection refused")

    monkeypatch.setattr(aioredis.Redis, "ping", failing_ping)

    await dispatcher.start()
    assert dispatcher._subscriber_task is None
    await dispatcher.stop()


@pytest.mark.asyncio
async def test_redis_publish_pushes_message(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    published = []

    class FakeRedis:
        async def publish(self, channel, message):
            published.append((channel, json.loads(message)))

        async def aclose(self):
            pass

    monkeypatch.setattr(aioredis, "from_url", lambda url, **kw: FakeRedis())

    await dispatcher._redis_publish({"type": "notification", "user_id": "u1"})
    assert len(published) == 1
    assert published[0][0] == "smartfeed:notifications"


@pytest.mark.asyncio
async def test_redis_publish_handles_failure(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    class BrokenRedis:
        async def publish(self, channel, message):
            raise ConnectionError("down")

        async def aclose(self):
            pass

    monkeypatch.setattr(aioredis, "from_url", lambda url, **kw: BrokenRedis())

    await dispatcher._redis_publish({"type": "notification"})
    # Should swallow the error.


class FakePubSub:
    def __init__(self, messages):
        self.messages = messages
        self.subscribed = []
        self.unsubscribed = False

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def unsubscribe(self, channel):
        self.unsubscribed = True

    async def listen(self):
        for message in self.messages:
            yield message


class FakePubsubClient:
    def __init__(self, messages):
        self.messages = messages
        self.closed = False

    async def ping(self):
        return True

    def pubsub(self):
        return FakePubSub(self.messages)

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_subscriber_routes_messages(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    payload = json.dumps({"type": "notification", "user_id": "u9", "notification": {"id": "n9"}})
    messages = [
        {"type": "subscribe", "data": 1},
        {"type": "message", "data": payload},
        {"type": "message", "data": "not-json"},
    ]

    monkeypatch.setattr(aioredis, "from_url", lambda url, **kw: FakePubsubClient(messages))

    await dispatcher.start()
    assert dispatcher._subscriber_task is not None

    # Let the subscriber consume all messages then stop.
    async def stop_later():
        await asyncio.sleep(0.1)
        await dispatcher.stop()

    await asyncio.gather(dispatcher._subscriber_task, stop_later())

    routed = [p for (u, p) in manager.sent if u == "u9"]
    assert routed, "expected the routed notification"
    assert routed[0]["notification"] == {"id": "n9"}


@pytest.mark.asyncio
async def test_subscriber_skips_invalid_payload(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    messages = [
        {"type": "message", "data": "definitely-not-json"},
    ]

    monkeypatch.setattr(aioredis, "from_url", lambda url, **kw: FakePubsubClient(messages))

    await dispatcher.start()

    async def stop_later():
        await asyncio.sleep(0.1)
        await dispatcher.stop()

    await asyncio.gather(dispatcher._subscriber_task, stop_later())
    assert manager.sent == []


@pytest.mark.asyncio
async def test_start_is_idempotent(monkeypatch):
    manager = FakeManager()
    dispatcher = NotificationDispatcher(manager=manager)

    async def failing_ping(self):
        raise OSError("no redis")

    monkeypatch.setattr(aioredis.Redis, "ping", failing_ping)
    await dispatcher.start()
    await dispatcher.start()
    assert dispatcher._subscriber_task is None


@pytest.mark.asyncio
async def test_stop_without_start(monkeypatch):
    dispatcher = NotificationDispatcher(manager=FakeManager())
    await dispatcher.stop()
    assert dispatcher._subscriber_task is None
    assert dispatcher._pubsub_client is None
