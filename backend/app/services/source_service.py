from uuid import UUID

from app.core.exceptions import DuplicateError, NotFoundError
from app.repositories.source_repository import SourceRepository
from app.schemas.source import SourceCreateRequest, SourceResponse


class SourceService:
    def __init__(self, source_repo: SourceRepository):
        self.source_repo = source_repo

    async def create_source(self, request: SourceCreateRequest) -> SourceResponse:
        existing = await self.source_repo.get_by_url(request.url)
        if existing:
            raise DuplicateError("Source with this URL already exists")

        source = await self.source_repo.create(**request.model_dump())
        return SourceResponse.model_validate(source)

    async def get_source(self, source_id: UUID) -> SourceResponse:
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise NotFoundError("Source not found")
        return SourceResponse.model_validate(source)

    async def get_sources(
        self,
        skip: int = 0,
        limit: int = 100,
        category: str | None = None,
        priority: str | None = None,
        active: bool | None = None,
    ) -> list[SourceResponse]:
        sources = await self.source_repo.get_all(skip, limit, "name", False)
        filtered = sources
        if category:
            filtered = [s for s in filtered if (s.category or "").lower() == category.lower()]
        if priority:
            filtered = [s for s in filtered if (s.priority or "").lower() == priority.lower()]
        if active is not None:
            filtered = [s for s in filtered if s.is_active == active]
        return [SourceResponse.model_validate(s) for s in filtered]

    async def update_source(self, source_id: UUID, data: dict) -> SourceResponse:
        # Handle field alias mappings for updates
        if "rss_url" in data and "feed_url" not in data:
            data["feed_url"] = data.pop("rss_url")
        if "active" in data and "is_active" not in data:
            data["is_active"] = data.pop("active")
        source = await self.source_repo.update(source_id, **data)
        if not source:
            raise NotFoundError("Source not found")
        return SourceResponse.model_validate(source)

    async def toggle_active(self, source_id: UUID) -> SourceResponse:
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise NotFoundError("Source not found")
        updated = await self.source_repo.update(source_id, is_active=not source.is_active)
        return SourceResponse.model_validate(updated)

    async def trigger_fetch(self, source_id: UUID) -> dict:
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise NotFoundError("Source not found")
        from app.services.article_ingestion_service import ArticleIngestionService

        async with ArticleIngestionService() as service:
            return await service.ingest_source(source_id)

    async def get_source_metrics(self, source_id: UUID) -> dict:
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise NotFoundError("Source not found")
        return {
            "source_id": str(source.id),
            "name": source.name,
            "category": source.category,
            "is_active": source.is_active,
            "priority": source.priority,
            "reliability_score": source.reliability_score,
            "rate_limit": source.rate_limit,
            "last_fetched_at": source.last_fetched_at,
            "last_fetch_success": source.last_fetch_success,
            "consecutive_failures": source.consecutive_failures,
        }

    async def delete_source(self, source_id: UUID) -> None:
        if not await self.source_repo.delete(source_id):
            raise NotFoundError("Source not found")

