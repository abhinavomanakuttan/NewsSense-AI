"""Unit tests for schema <-> ORM mapping (flattening helpers)."""

from datetime import UTC, datetime

from app.models.article import Article
from app.models.category import Category
from app.models.source import Source
from app.models.tag import Tag
from app.schemas.article import ArticleListResponse, ArticleResponse
from app.schemas.event import EventArticleResponse


def _make_article():
    source = Source(name="The Times", url="https://times.example", source_type="rss")
    category = Category(name="Science", slug="science")
    tag_a = Tag(name="Space", slug="space")
    tag_b = Tag(name="NASA", slug="nasa")
    return Article(
        id="11111111-2222-3333-4444-555555555555",
        title="Rocket Launch",
        slug="rocket-launch",
        url="https://times.example/rocket",
        content="Full text here.",
        summary="A rocket launched.",
        content_hash="deadbeef",
        source=source,
        category=category,
        tags=[tag_a, tag_b],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_article_response_flattens_relationships():
    article = _make_article()
    resp = ArticleResponse.model_validate(article)
    assert resp.source_name == "The Times"
    assert resp.category_name == "Science"
    assert resp.tags == ["Space", "NASA"]
    assert resp.title == "Rocket Launch"


def test_article_response_without_relationships():
    article = Article(
        id="11111111-2222-3333-4444-555555555555",
        title="Orphan Story",
        slug="orphan-story",
        url="https://times.example/orphan",
        content_hash="cafebabe",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    resp = ArticleResponse.model_validate(article)
    assert resp.source_name is None
    assert resp.category_name is None
    assert resp.tags == []


def test_article_list_response_flattens():
    article = _make_article()
    resp = ArticleListResponse.model_validate(article)
    assert resp.source_name == "The Times"
    assert resp.tags == ["Space", "NASA"]


def test_event_article_response_flattens():
    article = _make_article()
    resp = EventArticleResponse.model_validate(article)
    assert resp.source_name == "The Times"
