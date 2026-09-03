"""Tests for SearchService: ES path (fake ES), SQL fallback filters/sort, totals."""

from app.repositories.article_repository import ArticleRepository
from app.repositories.search_history_repository import SearchHistoryRepository
from app.schemas.search import SearchRequest
from app.services.search_service import SearchService


class FakeElasticsearchService:
    """In-memory Elasticsearch stand-in returning canned search responses."""

    def __init__(self, available: bool = True, response: dict | None = None):
        self.available = available
        self.response = response or {
            "total": 1,
            "hits": [
                {
                    "id": "art-1",
                    "score": 3.5,
                    "source": {
                        "title": "AI Breakthrough in Health",
                        "slug": "ai-breakthrough-health",
                        "summary": "AI helps doctors diagnose faster.",
                        "url": "https://testnews.com/ai-health",
                        "source_name": "Test News",
                        "category_name": "Technology",
                        "published_at": "2026-07-30T10:00:00",
                    },
                    "highlight": {"title": ["<em>AI</em> Breakthrough in Health"]},
                }
            ],
            "facets": {
                "categories": [("Technology", 1)],
                "sources": [("Test News", 1)],
                "sentiments": [],
            },
            "es": True,
        }
        self.calls: list[dict] = []

    async def is_available(self) -> bool:
        return self.available

    async def search(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return self.response


def build_service(db_session, es) -> SearchService:
    return SearchService(
        article_repo=ArticleRepository(db_session),
        search_history_repo=SearchHistoryRepository(db_session),
        elasticsearch_service=es,
    )


async def test_search_uses_es_when_available(db_session, article_fixture):
    es = FakeElasticsearchService()
    service = build_service(db_session, es)

    request = SearchRequest(query="AI", page=1, page_size=20)
    response = await service.search(request)

    assert len(es.calls) == 1
    assert es.calls[0]["query"] == "AI"
    assert response.total == 1
    assert response.results[0].title == "AI Breakthrough in Health"
    assert response.results[0].score == 3.5
    assert response.results[0].highlights == {"title": ["<em>AI</em> Breakthrough in Health"]}
    assert response.facets["categories"] == [("Technology", 1)]


async def test_search_es_passes_filters_and_sort(db_session, article_fixture):
    es = FakeElasticsearchService()
    service = build_service(db_session, es)

    request = SearchRequest(
        query="AI",
        category="Technology",
        source="Test News",
        language="en",
        sentiment="positive",
        sort_by="date",
        sort_order="desc",
    )
    await service.search(request)

    call = es.calls[0]
    assert call["filters"] == {
        "category": "Technology",
        "source": "Test News",
        "language": "en",
        "sentiment": "positive",
    }
    assert call["sort_by"] == "date"
    assert call["sort_order"] == "desc"


async def test_search_es_skips_none_filters(db_session, article_fixture):
    es = FakeElasticsearchService()
    service = build_service(db_session, es)

    await service.search(SearchRequest(query="AI", category=None, language=None))

    assert es.calls[0]["filters"] == {}


async def test_search_falls_back_to_sql_when_es_unavailable(db_session, article_fixture):
    es = FakeElasticsearchService(available=False)
    service = build_service(db_session, es)

    response = await service.search(SearchRequest(query="AI"))

    assert es.calls == []
    assert response.total == 1
    assert response.results[0].title == "AI Breakthrough in Health"
    assert response.facets is None


async def test_search_sql_filter_by_category(db_session, article_fixture, category_fixture):
    es = FakeElasticsearchService(available=False)
    service = build_service(db_session, es)

    response = await service.search(SearchRequest(query="AI", category="Technology", page_size=20))
    assert response.total == 1

    response = await service.search(
        SearchRequest(query="AI", category="Nonexistent Category", page_size=20)
    )
    assert response.total == 0


async def test_search_sql_filter_by_source(db_session, article_fixture, source_fixture):
    es = FakeElasticsearchService(available=False)
    service = build_service(db_session, es)

    response = await service.search(SearchRequest(query="AI", source="Test News"))
    assert response.total == 1

    response = await service.search(SearchRequest(query="AI", source="Other Source"))
    assert response.total == 0


async def test_search_sql_filter_by_language_and_sentiment(db_session, article_fixture):
    from sqlalchemy import update

    from app.models.article import Article

    await db_session.execute(
        update(Article).where(Article.id == article_fixture["id"]).values(sentiment="positive")
    )
    await db_session.commit()

    es = FakeElasticsearchService(available=False)
    service = build_service(db_session, es)

    response = await service.search(SearchRequest(query="AI", language="en", sentiment="positive"))
    assert response.total == 1

    response = await service.search(SearchRequest(query="AI", language="fr", sentiment="negative"))
    assert response.total == 0


async def test_search_sql_sort_by_date(db_session, article_fixture):
    es = FakeElasticsearchService(available=False)
    service = build_service(db_session, es)

    await ArticleRepository(db_session).create(
        title="AI in Agriculture",
        slug="ai-agriculture",
        url="https://testnews.com/ai-agriculture",
        content="AI transforms farming.",
        content_hash="test-hash-2",
        published_at="2026-07-31T10:00:00",
    )
    await db_session.commit()

    response = await service.search(SearchRequest(query="AI", sort_by="date", sort_order="asc"))
    assert response.total == 2
    assert response.results[0].title == "AI Breakthrough in Health"

    response = await service.search(SearchRequest(query="AI", sort_by="date", sort_order="desc"))
    assert response.results[0].title == "AI in Agriculture"
