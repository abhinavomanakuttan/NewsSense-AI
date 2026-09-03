from uuid import UUID

from app.repositories.article_repository import ArticleRepository
from app.repositories.search_history_repository import SearchHistoryRepository
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.elasticsearch_service import ElasticsearchService, get_elasticsearch_service


class SearchService:
    def __init__(
        self,
        article_repo: ArticleRepository,
        search_history_repo: SearchHistoryRepository,
        elasticsearch_service: ElasticsearchService | None = None,
    ):
        self.article_repo = article_repo
        self.search_history_repo = search_history_repo
        self.es = elasticsearch_service or get_elasticsearch_service()

    async def search(self, request: SearchRequest, user_id: str | None = None) -> SearchResponse:
        filters = {
            "category": request.category,
            "source": request.source,
            "language": request.language,
            "date_from": request.date_from,
            "date_to": request.date_to,
            "sentiment": request.sentiment,
        }

        es_used = await self.es.is_available()
        if es_used:
            response = await self._search_es(request, filters)
        else:
            response = await self._search_sql(request, filters)

        if user_id:
            await self.search_history_repo.create(
                user_id=UUID(user_id),
                query=request.query,
                filters=str(request.model_dump(exclude={"query", "page", "page_size"})),
                result_count=str(response.total),
            )

        return response

    async def _search_es(self, request: SearchRequest, filters: dict) -> SearchResponse:
        result = await self.es.search(
            query=request.query,
            page=request.page,
            page_size=request.page_size,
            filters={k: v for k, v in filters.items() if v is not None},
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )

        results = [
            SearchResultItem(
                id=hit["id"],
                title=hit["source"].get("title", ""),
                slug=hit["source"].get("slug", ""),
                summary=hit["source"].get("summary"),
                url=hit["source"].get("url", ""),
                source_name=hit["source"].get("source_name"),
                category_name=hit["source"].get("category_name"),
                published_at=hit["source"].get("published_at"),
                score=round(hit["score"], 4),
                highlights=hit["highlight"] or None,
            )
            for hit in result["hits"]
        ]

        return SearchResponse(
            query=request.query,
            total=result["total"],
            page=request.page,
            page_size=request.page_size,
            results=results,
            facets=result["facets"] or None,
        )

    async def _search_sql(self, request: SearchRequest, filters: dict) -> SearchResponse:
        offset = (request.page - 1) * request.page_size
        articles, total = await self.article_repo.search_by_keywords(
            request.query,
            skip=offset,
            limit=request.page_size,
            filters={k: v for k, v in filters.items() if v is not None},
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )

        results = [
            SearchResultItem(
                id=str(a.id),
                title=a.title,
                slug=a.slug,
                summary=a.summary,
                url=a.url,
                source_name=a.source.name if a.source else None,
                category_name=a.category.name if a.category else None,
                published_at=a.published_at,
                score=1.0,
            )
            for a in articles
        ]

        return SearchResponse(
            query=request.query,
            total=total,
            page=request.page,
            page_size=request.page_size,
            results=results,
            facets=None,
        )
