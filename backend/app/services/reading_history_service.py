from uuid import UUID

from app.core.exceptions import NotFoundError
from app.repositories.article_repository import ArticleRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.schemas.reading_history import (
    ReadingHistoryCreateRequest,
    ReadingHistoryListResponse,
    ReadingHistoryResponse,
)
from app.services.recommendation_service import invalidate_user_recommendations


class ReadingHistoryService:
    def __init__(
        self,
        history_repo: ReadingHistoryRepository,
        article_repo: ArticleRepository | None = None,
    ):
        self.history_repo = history_repo
        self.article_repo = article_repo

    async def record_reading(
        self, user_id: UUID, request: ReadingHistoryCreateRequest
    ) -> ReadingHistoryResponse:
        """Upsert a reading-history row per (user, article).

        Repeated reads of the same article accumulate duration instead of
        creating unbounded rows, keeping the history table compact.
        """
        if self.article_repo:
            article = await self.article_repo.get_by_id(request.article_id)
            if not article:
                raise NotFoundError("Article not found")

        existing = await self.history_repo.get_by_user_and_article(user_id, request.article_id)
        if existing:
            existing.read_duration_seconds += request.read_duration_seconds
            existing.scroll_depth = max(existing.scroll_depth, request.scroll_depth)
            await self.history_repo.db.flush()
            await self.history_repo.db.refresh(existing)
            await invalidate_user_recommendations(user_id)
            return ReadingHistoryResponse.model_validate(existing)

        record = await self.history_repo.create(
            user_id=user_id,
            article_id=request.article_id,
            read_duration_seconds=request.read_duration_seconds,
            scroll_depth=request.scroll_depth,
        )
        await invalidate_user_recommendations(user_id)
        return ReadingHistoryResponse.model_validate(record)

    async def get_history(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> ReadingHistoryListResponse:
        records = await self.history_repo.get_user_history(user_id, skip, limit)
        total = await self.history_repo.count_user_history(user_id)
        return ReadingHistoryListResponse(
            items=[ReadingHistoryResponse.model_validate(r) for r in records],
            total=total,
        )

    async def clear_history(self, user_id: UUID) -> int:
        """Delete a user's entire reading history, returning rows removed."""
        records = await self.history_repo.get_user_history(user_id, limit=100000)
        for record in records:
            await self.history_repo.delete(record.id)
        await invalidate_user_recommendations(user_id)
        return len(records)

    async def remove_record(self, user_id: UUID, history_id: UUID) -> None:
        """Delete a single reading-history record owned by the user."""
        if not await self.history_repo.remove_user_record(user_id, history_id):
            raise NotFoundError("Reading history record not found")
        await invalidate_user_recommendations(user_id)
