"""Unit tests for the pure utility helpers (no DB, no network)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import tenacity

from app.utils import cache, date_utils, pagination, text_utils
from app.utils.http_client import HttpClient


class TestParseDate:
    def test_none_returns_none(self):
        assert date_utils.parse_date(None) is None

    def test_naive_date_gets_utc(self):
        parsed = date_utils.parse_date("2026-07-30")
        assert parsed is not None
        assert parsed.tzinfo == UTC

    def test_aware_date_preserved(self):
        parsed = date_utils.parse_date("2026-07-30T10:00:00+05:00")
        assert parsed is not None
        assert parsed.utcoffset() is not None


class TestFormatDate:
    def test_default_format(self):
        dt = datetime(2026, 7, 30, 10, 0, 0, tzinfo=UTC)
        assert date_utils.format_date(dt) == "2026-07-30T10:00:00Z"

    def test_custom_format(self):
        dt = datetime(2026, 7, 30, 10, 0, 0, tzinfo=UTC)
        assert date_utils.format_date(dt, "%Y/%m/%d") == "2026/07/30"


class TestTimeAgo:
    def test_years(self):
        assert date_utils.time_ago(datetime.now(UTC) - timedelta(days=400)) == "1y ago"

    def test_months(self):
        assert date_utils.time_ago(datetime.now(UTC) - timedelta(days=100)) == "3mo ago"

    def test_days(self):
        assert date_utils.time_ago(datetime.now(UTC) - timedelta(days=10)) == "10d ago"

    def test_hours(self):
        assert date_utils.time_ago(datetime.now(UTC) - timedelta(hours=5)) == "5h ago"

    def test_minutes(self):
        assert date_utils.time_ago(datetime.now(UTC) - timedelta(minutes=5)) == "5m ago"

    def test_just_now(self):
        assert date_utils.time_ago(datetime.now(UTC) - timedelta(seconds=30)) == "just now"


class TestPaginator:
    def test_basic_pagination(self):
        pg = pagination.Paginator(items=[1, 2, 3], total=23, page=2, page_size=10)
        assert pg.total_pages == 3
        assert pg.has_next is True
        assert pg.has_prev is True

    def test_first_page(self):
        pg = pagination.Paginator(items=[1], total=1, page=1, page_size=10)
        assert pg.has_prev is False
        assert pg.has_next is False

    def test_empty_total(self):
        pg = pagination.Paginator(items=[], total=0, page=1, page_size=10)
        assert pg.total_pages == 1

    def test_to_dict(self):
        pg = pagination.Paginator(items=[1], total=5, page=1, page_size=5)
        data = pg.to_dict()
        assert data["total"] == 5
        assert data["page_size"] == 5
        assert data["has_next"] is False


class TestTextUtils:
    def test_slugify(self):
        assert text_utils.slugify("  AI News: Breakthrough!  ") == "ai-news-breakthrough"

    def test_slugify_unicode(self):
        assert text_utils.slugify("Café français") == "cafe-francais"

    def test_truncate_short(self):
        assert text_utils.truncate_text("hello", 10) == "hello"

    def test_truncate_long(self):
        text = "word " * 200
        result = text_utils.truncate_text(text, 50)
        assert result.endswith("...")
        assert len(result) <= 53

    def test_extract_content_hash(self):
        assert text_utils.extract_content_hash("a", "b") == text_utils.extract_content_hash(
            "a", "b"
        )
        assert text_utils.extract_content_hash("a", "b") != text_utils.extract_content_hash(
            "a", "c"
        )

    def test_strip_html(self):
        assert text_utils.strip_html("<p>Hello <b>world</b></p>") == "Hello world"


class TestHttpClient:
    def make_client(self, handler) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def test_get_success(self):
        def handler(request):
            return httpx.Response(200, json={"ok": True})

        http = HttpClient()
        http.client = self.make_client(handler)
        response = await http.get("https://example.com/data")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        await http.client.aclose()

    async def test_post_success(self):
        def handler(request):
            assert request.method == "POST"
            return httpx.Response(201, json={"id": 1})

        http = HttpClient()
        http.client = self.make_client(handler)
        response = await http.post("https://example.com/create", json={"a": 1})
        assert response.status_code == 201
        await http.client.aclose()

    async def test_lazy_client_creation(self, monkeypatch):
        original = httpx.AsyncClient

        created = []

        def fake_async_client(*args, **kwargs):
            client = original(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, text="lazy")),
                **kwargs,
            )
            created.append(client)
            return client

        monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)
        http = HttpClient()
        response = await http.get("https://example.com/lazy")
        assert response.text == "lazy"
        assert len(created) == 1
        assert http.client is created[0]
        await http.client.aclose()
        monkeypatch.setattr(httpx, "AsyncClient", original)

    async def test_context_manager(self):
        def handler(request):
            return httpx.Response(200)

        http = HttpClient()
        http.client = self.make_client(handler)
        async with http:
            assert http.client is not None
        # __aexit__ closed the client; calling close again is harmless
        assert http.client is not None

    async def test_http_error_raises_after_retries(self, monkeypatch):
        async def no_sleep(*args, **kwargs):
            return None

        monkeypatch.setattr("asyncio.sleep", no_sleep)

        def handler(request):
            return httpx.Response(500)

        http = HttpClient()
        http.client = self.make_client(handler)
        with pytest.raises(tenacity.RetryError):
            await http.get("https://example.com/error")
        await http.client.aclose()


class FakeRedisClient:
    def __init__(self):
        self.store: dict[str, str] = {}
        self._closed = False
        self.deleted: list[str] = []

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.store.pop(key, None)

    async def scan(self, cursor, match=None):
        prefix = match[:-1] if match and match.endswith("*") else match
        keys = [k for k in self.store if prefix is None or k.startswith(prefix)]
        return 0, keys

    async def close(self):
        self._closed = True


class TestCacheService:
    def build_service(self, monkeypatch) -> tuple[cache.CacheService, FakeRedisClient]:
        fake = FakeRedisClient()
        monkeypatch.setattr(cache.aioredis, "from_url", lambda url, **kw: fake)
        svc = cache.CacheService()
        return svc, fake

    async def test_uninitialized_returns_none(self):
        svc = cache.CacheService()
        assert await svc.get("key") is None
        assert await svc.set("key", 1) is None
        assert await svc.delete("key") is None

    async def test_set_get_roundtrip(self, monkeypatch):
        svc, fake = self.build_service(monkeypatch)
        await svc.initialize()
        await svc.set("a", {"x": 1}, ttl=60)
        assert await svc.get("a") == {"x": 1}
        assert await svc.get("missing") is None

    async def test_delete(self, monkeypatch):
        svc, fake = self.build_service(monkeypatch)
        await svc.initialize()
        await svc.set("a", 1)
        await svc.delete("a")
        assert await svc.get("a") is None

    async def test_invalidate_pattern(self, monkeypatch):
        svc, fake = self.build_service(monkeypatch)
        await svc.initialize()
        await svc.set("feed:1", 1)
        await svc.set("feed:2", 2)
        await svc.set("other", 3)
        await svc.invalidate_pattern("feed:*")
        assert "feed:1" in fake.deleted
        assert "other" not in fake.deleted

    async def test_close(self, monkeypatch):
        svc, fake = self.build_service(monkeypatch)
        await svc.initialize()
        await svc.close()
        assert fake._closed is True
