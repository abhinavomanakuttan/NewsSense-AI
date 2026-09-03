"""Unit tests for the Celery task wrappers, with heavy dependencies mocked."""

from types import SimpleNamespace
from uuid import uuid4

from app.pipeline.tasks import (
    enrichment,
    feed_fetcher,
    indexer,
    ner,
    recommendation_updater,
    sentiment,
)

UID = str(uuid4())


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def fake_session_factory():
    return FakeSession()


class TestFeedFetcher:
    async def test_ingest_source(self, monkeypatch):
        result = {"new_article_ids": ["a1"], "new": 1}

        class FakeIngestionService:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def ingest_source(self, source_id):
                return result

        monkeypatch.setattr(feed_fetcher, "ArticleIngestionService", FakeIngestionService)
        out = await feed_fetcher._ingest_source(UID)
        assert out == result

    async def test_dispatch_all_sources(self, monkeypatch):
        dispatched = []

        class FakeId:
            def __str__(self):
                return "src-id"

        fake_source = SimpleNamespace(id=FakeId(), is_active=True)

        session = FakeSession()

        async def execute(stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [fake_source]))

        session.execute = execute
        session.expunge_all = lambda: None

        monkeypatch.setattr(feed_fetcher, "async_session_factory", lambda: session)

        class FakeTask:
            @staticmethod
            def delay(source_id):
                dispatched.append(source_id)

        monkeypatch.setattr(feed_fetcher, "fetch_source", FakeTask)

        out = await feed_fetcher._dispatch_all_sources()
        assert out["dispatched"] == 1
        assert dispatched == ["src-id"]

    def test_fetch_newsapi_no_key(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.newsapi_key", None)
        result = feed_fetcher.fetch_newsapi(query="ai")
        assert result["error"] == "API key not configured"

    def test_fetch_newsapi_with_key(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.newsapi_key", "key")
        result = feed_fetcher.fetch_newsapi(query="ai")
        assert result["status"] == "not_configured"

    def test_fetch_rss_feed_calls_fetch_source(self, monkeypatch):
        called = []

        class FakeTask:
            @staticmethod
            def __call__(source_id):
                called.append(source_id)
                return {"ok": True}

        monkeypatch.setattr(feed_fetcher, "fetch_source", FakeTask())
        result = feed_fetcher.fetch_rss_feed("http://feed", "src-1")
        assert result == {"ok": True}
        assert called == ["src-1"]


class TestEnrichmentTask:
    def test_enrich_article_success(self, monkeypatch):
        async def fake_enrich(article_id):
            return {"article_id": article_id, "enriched": True}

        monkeypatch.setattr(enrichment, "_enrich", fake_enrich)
        result = enrichment.enrich_article("a1")
        assert result == {"article_id": "a1", "enriched": True}


class TestSentimentTask:
    def test_analyze_sentiment(self, monkeypatch):
        class FakeAnalyzer:
            def __init__(self):
                self.initialized = False
                self.cleaned = False

            async def initialize(self):
                self.initialized = True

            async def process(self, data):
                return {"sentiment": "positive"}

            async def cleanup(self):
                self.cleaned = True

        fake = FakeAnalyzer()
        monkeypatch.setattr(sentiment, "SentimentAnalyzer", lambda: fake)
        result = sentiment.analyze_sentiment({"title": "t"})
        assert result == {"sentiment": "positive"}
        assert fake.initialized and fake.cleaned


class TestNERTask:
    def test_extract_entities(self, monkeypatch):
        class FakeExtractor:
            def __init__(self):
                self.initialized = False
                self.cleaned = False

            async def initialize(self):
                self.initialized = True

            async def process(self, data):
                return {"entity_count": 2}

            async def cleanup(self):
                self.cleaned = True

        fake = FakeExtractor()
        monkeypatch.setattr(ner, "NERExtractor", lambda: fake)
        result = ner.extract_entities({"title": "t"})
        assert result == {"entity_count": 2}
        assert fake.initialized and fake.cleaned


class TestIndexer:
    def make_fake_es(self, available=True, index_ok=True, removed=True):
        class FakeES:
            def __init__(self):
                self.deleted = None

            async def is_available(self):
                return available

            async def index_document(self, article_id, document):
                return index_ok

            async def delete_document(self, article_id):
                return removed

        return FakeES()

    def test_index_article_es_unavailable(self, monkeypatch):
        fake = self.make_fake_es(available=False)
        monkeypatch.setattr(indexer, "get_elasticsearch_service", lambda: fake)
        result = indexer.index_article({"id": UID})
        assert result["indexed"] is False
        assert result["reason"] == "elasticsearch_unavailable"

    def test_index_article_missing_id(self, monkeypatch):
        fake = self.make_fake_es()
        monkeypatch.setattr(indexer, "get_elasticsearch_service", lambda: fake)
        result = indexer.index_article({})
        assert result["indexed"] is False
        assert result["error"] == "no id"

    def test_index_article_not_found(self, monkeypatch):
        fake = self.make_fake_es()
        monkeypatch.setattr(indexer, "get_elasticsearch_service", lambda: fake)

        class Repo:
            def __init__(self, session):
                self.session = session

            async def get_by_id(self, article_id):
                return None

        monkeypatch.setattr(indexer, "async_session_factory", fake_session_factory)
        monkeypatch.setattr(indexer, "ArticleRepository", Repo)

        result = indexer.index_article({"id": UID})
        assert result["error"] == "not found"

    def test_index_article_success(self, monkeypatch):
        fake = self.make_fake_es()
        monkeypatch.setattr(indexer, "get_elasticsearch_service", lambda: fake)

        class Repo:
            def __init__(self, session):
                self.session = session

            async def get_by_id(self, article_id):
                return SimpleNamespace(id=article_id)

        monkeypatch.setattr(indexer, "async_session_factory", fake_session_factory)
        monkeypatch.setattr(indexer, "ArticleRepository", Repo)
        monkeypatch.setattr(indexer, "build_article_document", lambda article: {"title": "x"})

        result = indexer.index_article({"id": UID})
        assert result["indexed"] is True
        assert result["es"] is True

    def test_remove_from_index(self, monkeypatch):
        fake = self.make_fake_es(removed=True)
        monkeypatch.setattr(indexer, "get_elasticsearch_service", lambda: fake)
        result = indexer.remove_from_index(UID)
        assert result["removed"] is True


class TestRecommendationUpdater:
    async def test_update_trending_caches(self, monkeypatch):
        class FakeId:
            def __str__(self):
                return "art-1"

        article = SimpleNamespace(
            id=FakeId(),
            title="T",
            slug="t",
            view_count="1",
            credibility_score=0.9,
            published_at="2026-07-30",
            image_url=None,
            source=SimpleNamespace(name="S"),
            category=SimpleNamespace(name="C"),
        )

        class Repo:
            def __init__(self, session):
                self.session = session

            async def get_trending(self, limit):
                return [article]

        monkeypatch.setattr(recommendation_updater, "async_session_factory", fake_session_factory)
        monkeypatch.setattr(recommendation_updater, "ArticleRepository", Repo)

        cached = {}

        async def fake_set(key, value, ttl):
            cached[key] = value

        async def fake_init():
            return None

        monkeypatch.setattr(recommendation_updater.cache_service, "set", fake_set)
        monkeypatch.setattr(recommendation_updater.cache_service, "initialize", fake_init)

        result = await recommendation_updater._update_trending()
        assert result["count"] == 1
        assert list(cached) == [recommendation_updater.TRENDING_CACHE_KEY]

    async def test_update_trending_redis_failure(self, monkeypatch):
        class Repo:
            def __init__(self, session):
                self.session = session

            async def get_trending(self, limit):
                return []

        monkeypatch.setattr(recommendation_updater, "async_session_factory", fake_session_factory)
        monkeypatch.setattr(recommendation_updater, "ArticleRepository", Repo)

        async def fail_set(key, value, ttl):
            raise ConnectionError("redis down")

        async def fake_init():
            return None

        monkeypatch.setattr(recommendation_updater.cache_service, "set", fail_set)
        monkeypatch.setattr(recommendation_updater.cache_service, "initialize", fake_init)

        result = await recommendation_updater._update_trending()
        assert result["status"] == "trending_updated"
        assert result["cached"] is False

    async def test_update_user_recommendations(self, monkeypatch):
        class Rec:
            def model_dump(self, mode="python"):
                return {"slug": "t"}

        class Service:
            async def get_recommendations(self, user_id, limit, use_cache):
                return [Rec()]

        monkeypatch.setattr(recommendation_updater, "async_session_factory", fake_session_factory)
        monkeypatch.setattr(
            recommendation_updater.RecommendationService,
            "get_recommendations",
            Service().get_recommendations,
        )

        cached = {}

        async def fake_set(key, value, ttl):
            cached[key] = value

        async def fake_init():
            return None

        monkeypatch.setattr(recommendation_updater.cache_service, "set", fake_set)
        monkeypatch.setattr(recommendation_updater.cache_service, "initialize", fake_init)

        result = await recommendation_updater._update_user_recommendations(UID)
        assert result["status"] == "updated"
        assert result["count"] == 1
