"""Tests for AI enrichment (model-free: fake modules injected)."""

from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.models.article import Article
from app.models.category import Category
from app.services.article_enrichment_service import ArticleEnrichmentService


class FakeModule:
    def __init__(self, result: dict):
        self.result = result
        self.initialized = False
        self.cleaned = False

    async def initialize(self) -> None:
        self.initialized = True

    async def process(self, data: dict, **kwargs) -> dict:
        return self.result

    async def cleanup(self) -> None:
        self.cleaned = True


class FakeVectorStore:
    def __init__(self):
        self.points = {}
        self.available = True

    def is_available(self) -> bool:
        return self.available

    def upsert(
        self, article_id: str, embedding: list[float], payload: dict | None = None
    ) -> str | None:
        point_id = f"article_{article_id}"
        self.points[point_id] = {"embedding": embedding, "payload": payload}
        return point_id

    def remove(self, article_id: str) -> bool:
        key = f"article_{article_id}"
        return key in self.points and self.points.pop(key, None) is not None

    def search(self, embedding, limit=10, score_threshold=None) -> list[dict]:
        return [{"id": k, "score": 0.9, "payload": v["payload"]} for k, v in self.points.items()]


def build_modules():
    return {
        "classifier": FakeModule({"category": "technology", "confidence": 0.95}),
        "sentiment": FakeModule({"sentiment": "positive", "score": 0.92, "label": "positive"}),
        "ner": FakeModule(
            {
                "entities": [{"text": "OpenAI", "label": "ORG"}],
                "entity_count": 1,
                "keywords": ["openai"],
                "entities_json": '[{"text": "OpenAI", "label": "ORG"}]',
                "keywords_json": '["openai"]',
            }
        ),
        "credibility": FakeModule(
            {
                "credibility_score": 0.8,
                "verdict": "likely_true",
                "factors": [{"name": "source_reputation", "score": 0.8, "weight": 0.3}],
            }
        ),
        "summarizer": FakeModule({"summary": "A concise AI summary.", "compression_ratio": 0.4}),
        "embeddings": FakeModule({"embedding": [0.1, 0.2, 0.3], "dimension": 3, "model": "fake"}),
    }


def build_enrichment(db_session, modules=None, vector_store=None):
    return ArticleEnrichmentService(
        session=db_session,
        modules=modules or build_modules(),
        vector_store=vector_store or FakeVectorStore(),
    )


async def test_enrich_article_persists_fields(db_session, article_fixture):
    service = build_enrichment(db_session)
    result = await service.enrich_article(article_fixture["id"])

    assert result["steps"]["classifier"]["status"] == "success"
    assert result["steps"]["sentiment"]["status"] == "success"
    assert result["steps"]["ner"]["status"] == "success"
    assert result["steps"]["embeddings"]["status"] == "success"

    article = (
        await db_session.execute(select(Article).where(Article.id == article_fixture["id"]))
    ).scalar()
    assert article.sentiment == "positive"
    assert article.sentiment_score == 0.92
    assert article.keywords == '["openai"]'
    assert article.credibility_score == 0.8
    assert article.embedding_id == f"article_{article_fixture['id']}"

    category = (
        await db_session.execute(select(Category).where(Category.slug == "technology"))
    ).scalar()
    assert category is not None
    assert article.category_id == category.id


async def test_enrich_article_missing_raises(db_session):
    service = build_enrichment(db_session)
    with pytest.raises(ValueError):
        await service.enrich_article(uuid4())


async def test_enrich_isolates_failing_module(db_session, article_fixture):
    async def boom(data, **kwargs):
        raise RuntimeError("model exploded")

    modules = build_modules()
    failing = FakeModule({})
    failing.process = boom
    modules["classifier"] = failing

    service = build_enrichment(db_session, modules=modules)
    result = await service.enrich_article(article_fixture["id"])

    assert result["steps"]["classifier"]["status"] == "failed"
    assert result["steps"]["sentiment"]["status"] == "success"


async def test_enrich_uninitialized_module_skipped(db_session, article_fixture):
    modules = build_modules()
    modules["summarizer"] = object()  # not an AIModule; no initialize()

    service = build_enrichment(db_session, modules=modules)
    result = await service.enrich_article(article_fixture["id"])

    assert result["steps"]["summarizer"]["status"] == "skipped"


async def test_summarizer_skips_when_summary_exists(db_session, article_fixture):
    modules = build_modules()
    modules["summarizer"] = FakeModule(
        {"summary": "Should not override.", "compression_ratio": 0.3}
    )

    long_summary = " ".join(["word"] * 30)
    await db_session.execute(
        update(Article).where(Article.id == article_fixture["id"]).values(summary=long_summary)
    )
    await db_session.commit()

    service = build_enrichment(db_session, modules=modules)
    result = await service.enrich_article(article_fixture["id"])
    assert result["steps"]["summarizer"]["status"] == "skipped"
