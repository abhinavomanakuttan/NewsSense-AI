"""Elasticsearch service for full-text article search.

Mirrors the graceful-degradation pattern of `vector_store_service.py`: if
Elasticsearch is unreachable the service reports itself unavailable and the
search path falls back to the SQL implementation. All operations are async.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "articles"

INDEX_MAPPINGS: dict[str, Any] = {
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "summary": {"type": "text"},
            "content": {"type": "text"},
            "keywords": {"type": "text"},
            "slug": {"type": "keyword"},
            "url": {"type": "keyword"},
            "source_name": {"type": "keyword"},
            "category_name": {"type": "keyword"},
            "language": {"type": "keyword"},
            "sentiment": {"type": "keyword"},
            "published_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
            "credibility_score": {"type": "float"},
            "view_count": {"type": "long"},
        }
    }
}


class ElasticsearchService:
    def __init__(self, hosts: str | None = None, api_key: str | None = None):
        self.hosts = hosts or settings.elasticsearch_hosts
        self.api_key = api_key if api_key is not None else settings.elasticsearch_api_key
        self._client: Any | None = None
        self._available: bool | None = None

    def _get_client(self):
        if self._client is None:
            from elasticsearch import AsyncElasticsearch

            kwargs: dict[str, Any] = {
                "hosts": self.hosts,
                "request_timeout": 10,
                "max_retries": 0,
                "retry_on_timeout": False,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = AsyncElasticsearch(**kwargs)
        return self._client

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            self._available = bool(await self._get_client().ping())
        except Exception:
            self._available = False
            logger.warning(f"Elasticsearch unreachable at {self.hosts}; falling back to SQL search")
        return self._available

    async def ensure_index(self) -> bool:
        if not await self.is_available():
            return False
        try:
            client = self._get_client()
            if not await client.indices.exists(index=INDEX_NAME):
                await client.indices.create(index=INDEX_NAME, body=INDEX_MAPPINGS)
            return True
        except Exception as exc:
            logger.error(f"Failed to ensure Elasticsearch index: {exc}")
            return False

    async def index_document(self, article_id: str, document: dict) -> bool:
        """Index an article document; returns True on success."""
        if not await self.is_available():
            return False
        try:
            await self.ensure_index()
            await self._get_client().index(index=INDEX_NAME, id=article_id, document=document)
            return True
        except Exception as exc:
            logger.error(f"Elasticsearch index failed for {article_id}: {exc}")
            return False

    async def delete_document(self, article_id: str) -> bool:
        if not await self.is_available():
            return False
        try:
            await self._get_client().delete(index=INDEX_NAME, id=article_id)
            return True
        except Exception as exc:
            logger.error(f"Elasticsearch delete failed for {article_id}: {exc}")
            return False

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
        filters: dict | None = None,
        sort_by: str = "relevance",
        sort_order: str = "desc",
    ) -> dict:
        """Full-text search with filters, sorting, highlighting, and facets."""
        if not await self.is_available():
            return {"total": 0, "hits": [], "facets": {}, "es": False}

        filters = filters or {}
        body = self._build_query(query, filters, sort_by, sort_order)

        from_size = (page - 1) * page_size
        body["from"] = from_size
        body["size"] = page_size

        try:
            response = await self._get_client().search(
                index=INDEX_NAME,
                body=body,
            )
        except Exception as exc:
            logger.error(f"Elasticsearch search failed: {exc}")
            return {"total": 0, "hits": [], "facets": {}, "es": True, "error": str(exc)}

        total = response["hits"]["total"]["value"]
        hits = [
            {
                "id": hit["_id"],
                "score": hit["_score"] or 0.0,
                "source": hit["_source"],
                "highlight": hit.get("highlight", {}),
            }
            for hit in response["hits"]["hits"]
        ]
        facets = {
            name: [(b["key"], b["doc_count"]) for b in agg["buckets"]]
            for name, agg in response.get("aggregations", {}).items()
        }
        return {"total": total, "hits": hits, "facets": facets, "es": True}

    def _build_query(self, query: str, filters: dict, sort_by: str, sort_order: str) -> dict:
        must: list[dict] = []
        filter_clauses: list[dict] = []

        if query.strip():
            must.append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "title^3",
                            "summary^2",
                            "keywords^2",
                            "content",
                        ],
                        "type": "best_fields",
                    }
                }
            )
        else:
            must.append({"match_all": {}})

        if filters.get("category"):
            filter_clauses.append({"term": {"category_name": filters["category"]}})
        if filters.get("source"):
            filter_clauses.append({"term": {"source_name": filters["source"]}})
        if filters.get("language"):
            filter_clauses.append({"term": {"language": filters["language"]}})
        if filters.get("sentiment"):
            filter_clauses.append({"term": {"sentiment": filters["sentiment"]}})

        date_range: dict[str, str] = {}
        if filters.get("date_from"):
            date_range["gte"] = filters["date_from"]
        if filters.get("date_to"):
            date_range["lte"] = filters["date_to"]
        if date_range:
            filter_clauses.append({"range": {"published_at": date_range}})

        query_body: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses,
                }
            },
            "highlight": {
                "fields": {
                    "title": {"fragment_size": 120, "number_of_fragments": 1},
                    "summary": {"fragment_size": 180, "number_of_fragments": 1},
                }
            },
            "aggs": {
                "categories": {"terms": {"field": "category_name", "size": 20}},
                "sources": {"terms": {"field": "source_name", "size": 20}},
                "sentiments": {"terms": {"field": "sentiment", "size": 10}},
            },
        }

        if sort_by == "date":
            query_body["sort"] = [{"published_at": {"order": sort_order}}]
        elif sort_by == "view_count":
            query_body["sort"] = [{"view_count": {"order": sort_order}}]
        elif sort_by == "credibility":
            query_body["sort"] = [{"credibility_score": {"order": sort_order}}]
        # relevance: default ES _score ordering

        return query_body


def get_elasticsearch_service() -> ElasticsearchService:
    return ElasticsearchService()


def build_article_document(article: Any) -> dict:
    """Build an Elasticsearch document from an Article ORM object."""
    try:
        view_count = int(article.view_count or 0)
    except (TypeError, ValueError):
        view_count = 0

    return {
        "title": article.title,
        "slug": article.slug,
        "url": article.url,
        "summary": article.summary or "",
        "content": article.content or "",
        "keywords": article.keywords or "",
        "source_name": article.source.name if article.source else None,
        "category_name": article.category.name if article.category else None,
        "language": article.language,
        "sentiment": article.sentiment,
        "published_at": article.published_at,
        "credibility_score": article.credibility_score,
        "view_count": view_count,
    }
