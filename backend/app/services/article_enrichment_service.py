"""AI enrichment service.

Runs the AI modules (classifier, sentiment, NER, credibility, summarizer,
embeddings) against a persisted article and writes the results back to the
Article row. Modules are injectable so tests can substitute fakes without
loading heavyweight models. Each module is fault-isolated: a failure in one
step never prevents the others from running.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classifier import NewsClassifier
from app.ai.credibility import CredibilityAssessor
from app.ai.embeddings import EmbeddingGenerator
from app.ai.ner import NERExtractor
from app.ai.sentiment import SentimentAnalyzer
from app.ai.summarizer import NewsSummarizer
from app.core.metrics import ENRICHMENT_RUNS_TOTAL
from app.db.session import async_session_factory
from app.repositories.article_repository import ArticleRepository
from app.repositories.category_repository import CategoryRepository
from app.services.vector_store_service import VectorStoreService, get_vector_store

logger = logging.getLogger(__name__)

DEFAULT_MODULES = {
    "classifier": NewsClassifier,
    "sentiment": SentimentAnalyzer,
    "ner": NERExtractor,
    "credibility": CredibilityAssessor,
    "summarizer": NewsSummarizer,
    "embeddings": EmbeddingGenerator,
}

# Names of modules that persist results back to the Article row.
PERSISTING_MODULES = {
    "classifier",
    "sentiment",
    "ner",
    "credibility",
    "summarizer",
    "embeddings",
}


class ArticleEnrichmentService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        modules: dict[str, Any] | None = None,
        vector_store: VectorStoreService | None = None,
        elasticsearch_service: Any | None = None,
    ):
        self._owns_session = session is None
        self.session = session or async_session_factory()
        self.article_repo = ArticleRepository(self.session)
        self.category_repo = CategoryRepository(self.session)
        self.vector_store = vector_store or get_vector_store()
        self.es = elasticsearch_service
        self._modules: dict[str, Any] | None = None
        self.module_factories = modules or DEFAULT_MODULES

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._cleanup_modules()
        if self._owns_session:
            await self.session.close()

    async def _ensure_modules(self) -> None:
        if self._modules is not None:
            return
        self._modules = {}
        for name, factory in self.module_factories.items():
            try:
                module = factory() if isinstance(factory, type) else factory
                await module.initialize()
                self._modules[name] = module
            except Exception as exc:
                logger.warning(f"Module '{name}' failed to initialize: {exc}")
                self._modules[name] = None

    async def _cleanup_modules(self) -> None:
        if not self._modules:
            return
        from contextlib import suppress

        for module in self._modules.values():
            if module is None:
                continue
            with suppress(Exception):
                await module.cleanup()
        self._modules = None

    async def enrich_article(self, article_id: UUID | str) -> dict:
        ENRICHMENT_RUNS_TOTAL.inc()
        article = await self.article_repo.get_by_id(UUID(str(article_id)))
        if not article:
            raise ValueError(f"Article {article_id} not found")

        await self._ensure_modules()
        article_data = self._article_payload(article)

        results: dict[str, Any] = {}
        for name in PERSISTING_MODULES:
            module = self._modules.get(name) if self._modules else None
            if module is None:
                results[name] = {"status": "skipped"}
                continue
            try:
                if name == "classifier":
                    out = await module.process(article_data)
                    results[name] = await self._apply_classification(article, out)
                elif name == "sentiment":
                    out = await module.process(article_data)
                    article.sentiment = out.get("sentiment")
                    article.sentiment_score = out.get("score")
                    results[name] = {"status": "success", **out}
                elif name == "ner":
                    out = await module.process(article_data)
                    article.keywords = out.get("keywords_json")
                    article.entities = out.get("entities_json")
                    results[name] = {
                        "status": "success",
                        "entity_count": out.get("entity_count"),
                        "keywords": out.get("keywords"),
                    }
                elif name == "credibility":
                    similar = await self._similar_articles(article)
                    out = await module.process(
                        {
                            "article": article_data,
                            "source": self._source_payload(article),
                            "similar_articles": similar,
                        }
                    )
                    article.credibility_score = out.get("credibility_score")
                    article.credibility_factors = json.dumps(out.get("factors", []))
                    results[name] = {
                        "status": "success",
                        "credibility_score": out.get("credibility_score"),
                        "verdict": out.get("verdict"),
                    }
                elif name == "summarizer":
                    if article.summary and len(article.summary.split()) >= 25:
                        results[name] = {"status": "skipped", "reason": "summary_exists"}
                        continue
                    out = await module.process(article_data)
                    if out.get("summary"):
                        article.summary = out["summary"]
                    results[name] = {
                        "status": "success",
                        "compression_ratio": out.get("compression_ratio"),
                    }
                elif name == "embeddings":
                    out = await module.process(article_data)
                    point_id = self.vector_store.upsert(
                        str(article.id),
                        out.get("embedding", []),
                        payload={
                            "title": article.title,
                            "slug": article.slug,
                            "url": article.url,
                        },
                    )
                    if point_id:
                        article.embedding_id = point_id
                    results[name] = {
                        "status": "success" if point_id else "stored_locally",
                        "point_id": point_id,
                        "dimension": out.get("dimension"),
                    }
            except Exception as exc:
                logger.error(f"Enrichment step '{name}' failed for {article.id}: {exc}")
                results[name] = {"status": "failed", "error": str(exc)}

        await self.session.flush()
        if self._owns_session:
            await self.session.commit()

        if self._owns_session:
            await self._index_article(article)
            await self._dispatch_new_article_notifications(article)

        return {"article_id": str(article.id), "steps": results}

    async def _dispatch_new_article_notifications(self, article: Any) -> None:
        """Notify users who follow the article's category (best-effort)."""
        if not article.category_id:
            return
        try:
            from app.services.notification_producer import ArticleNotificationProducer

            producer = ArticleNotificationProducer()
            created = await producer.notify_for_article(str(article.id))
            if created:
                logger.info(f"Sent {created} new-article notifications for {article.id}")
        except Exception as exc:
            logger.warning(f"New-article notifications failed for {article.id}: {exc}")

    async def _index_article(self, article: Any) -> None:
        from app.services.elasticsearch_service import (
            build_article_document,
            get_elasticsearch_service,
        )

        es = self.es or get_elasticsearch_service()
        if not await es.is_available():
            return
        try:
            await es.index_document(str(article.id), build_article_document(article))
        except Exception as exc:
            logger.warning(f"ES indexing failed for {article.id}: {exc}")

    async def _apply_classification(self, article: Any, out: dict) -> dict:
        category_slug = (out.get("category") or "").strip()
        if not category_slug:
            return {"status": "success", "category": None, "confidence": out.get("confidence")}
        category = await self.category_repo.get_by_slug(category_slug)
        if not category:
            try:
                category = await self.category_repo.create(
                    name=category_slug.replace("-", " ").title(), slug=category_slug
                )
            except Exception:
                category = None
        if category:
            article.category_id = category.id
        return {
            "status": "success",
            "category": category_slug,
            "category_id": str(category.id) if category else None,
            "confidence": out.get("confidence"),
        }

    async def _similar_articles(self, article: Any) -> list[dict]:
        similar = (
            await self.article_repo.get_by_category(article.category_id, limit=5)
            if article.category_id
            else []
        )
        return [
            {
                "id": str(a.id),
                "title": a.title,
                "content_hash": a.content_hash,
                "credibility_score": a.credibility_score or 0,
            }
            for a in similar
            if a.id != article.id
        ]

    @staticmethod
    def _article_payload(article: Any) -> dict:
        return {
            "id": str(article.id),
            "title": article.title,
            "content": article.content or "",
            "summary": article.summary or "",
            "slug": article.slug,
            "url": article.url,
            "category": article.category.name if article.category else None,
            "published_at": article.published_at,
        }

    @staticmethod
    def _source_payload(article: Any) -> dict:
        source = article.source
        return {
            "id": str(source.id) if source else None,
            "name": source.name if source else "unknown",
            "reputation_score": source.reputation_score if source else 0.5,
        }
