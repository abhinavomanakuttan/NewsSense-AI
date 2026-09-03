"""Unit tests for the Elasticsearch service (query builder, document builder).

These tests never touch a real Elasticsearch instance; they exercise the pure
logic of `ElasticsearchService` that can be tested without a server.
"""

import pytest

from app.services.elasticsearch_service import ElasticsearchService, build_article_document


class FakeArticle:
    def __init__(self):
        self.title = "AI Breakthrough in Health"
        self.slug = "ai-breakthrough-health"
        self.url = "https://testnews.com/ai-health"
        self.summary = "AI helps doctors diagnose faster."
        self.content = "Scientists announced a breakthrough in AI-assisted diagnostics."
        self.keywords = '["ai", "health"]'
        self.language = "en"
        self.sentiment = "positive"
        self.published_at = "2026-07-30T10:00:00"
        self.credibility_score = 0.8
        self.view_count = "42"
        self.source = type("Source", (), {"name": "Test News"})()
        self.category = type("Category", (), {"name": "Technology"})()


def build_service() -> ElasticsearchService:
    return ElasticsearchService(hosts="http://es-test:9200")


def test_build_query_empty_query_uses_match_all():
    body = build_service()._build_query("   ", {}, "relevance", "desc")
    assert body["query"]["bool"]["must"][0] == {"match_all": {}}


def test_build_query_multi_match_fields_with_boost():
    body = build_service()._build_query("health", {}, "relevance", "desc")
    clause = body["query"]["bool"]["must"][0]["multi_match"]
    assert clause["query"] == "health"
    assert clause["fields"] == ["title^3", "summary^2", "keywords^2", "content"]


def test_build_query_applies_filters():
    service = build_service()
    filters = {
        "category": "Technology",
        "source": "Test News",
        "language": "en",
        "sentiment": "positive",
        "date_from": "2026-07-01T00:00:00",
        "date_to": "2026-07-31T23:59:59",
    }
    body = service._build_query("health", filters, "relevance", "desc")
    clauses = body["query"]["bool"]["filter"]
    assert {"term": {"category_name": "Technology"}} in clauses
    assert {"term": {"source_name": "Test News"}} in clauses
    assert {"term": {"language": "en"}} in clauses
    assert {"term": {"sentiment": "positive"}} in clauses
    assert {
        "range": {"published_at": {"gte": "2026-07-01T00:00:00", "lte": "2026-07-31T23:59:59"}}
    } in clauses


def test_build_query_sort_variants():
    service = build_service()
    assert service._build_query("q", {}, "date", "desc")["sort"] == [
        {"published_at": {"order": "desc"}}
    ]
    assert service._build_query("q", {}, "date", "asc")["sort"] == [
        {"published_at": {"order": "asc"}}
    ]
    assert service._build_query("q", {}, "view_count", "asc")["sort"] == [
        {"view_count": {"order": "asc"}}
    ]
    assert service._build_query("q", {}, "credibility", "desc")["sort"] == [
        {"credibility_score": {"order": "desc"}}
    ]
    assert "sort" not in service._build_query("q", {}, "relevance", "desc")


def test_build_query_includes_highlight_and_aggs():
    body = build_service()._build_query("health", {}, "relevance", "desc")
    assert "highlight" in body
    assert set(body["highlight"]["fields"]) == {"title", "summary"}
    assert set(body["aggs"]) == {"categories", "sources", "sentiments"}


def test_build_article_document():
    doc = build_article_document(FakeArticle())
    assert doc["title"] == "AI Breakthrough in Health"
    assert doc["source_name"] == "Test News"
    assert doc["category_name"] == "Technology"
    assert doc["view_count"] == 42
    assert doc["sentiment"] == "positive"


def test_build_article_document_handles_missing_relations():
    article = FakeArticle()
    article.source = None
    article.category = None
    article.view_count = None
    doc = build_article_document(article)
    assert doc["source_name"] is None
    assert doc["category_name"] is None
    assert doc["view_count"] == 0


def test_build_article_document_handles_bad_view_count():
    article = FakeArticle()
    article.view_count = "not-a-number"
    assert build_article_document(article)["view_count"] == 0


@pytest.mark.asyncio
async def test_is_available_returns_false_when_ping_fails(monkeypatch):
    service = ElasticsearchService(hosts="http://es-test:9200")

    class FakeClient:
        async def ping(self):
            return False

        async def close(self):
            pass

    monkeypatch.setattr(service, "_get_client", lambda: FakeClient())
    assert await service.is_available() is False


@pytest.mark.asyncio
async def test_is_available_returns_true_when_ping_succeeds(monkeypatch):
    service = ElasticsearchService(hosts="http://es-test:9200")

    class FakeClient:
        async def ping(self):
            return True

        async def close(self):
            pass

    monkeypatch.setattr(service, "_get_client", lambda: FakeClient())
    assert await service.is_available() is True


@pytest.mark.asyncio
async def test_is_available_caches_result(monkeypatch):
    service = ElasticsearchService(hosts="http://es-test:9200")
    calls = {"n": 0}

    class FakeClient:
        async def ping(self):
            calls["n"] += 1
            return False

        async def close(self):
            pass

    monkeypatch.setattr(service, "_get_client", lambda: FakeClient())
    assert await service.is_available() is False
    assert await service.is_available() is False
    assert calls["n"] == 1
