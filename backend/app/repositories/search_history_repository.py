from uuid import UUID

from sqlalchemy import select

from app.models.search_history import SearchHistory
from app.repositories.base import BaseRepository


class SearchHistoryRepository(BaseRepository[SearchHistory]):
    def __init__(self, db):
        super().__init__(db, SearchHistory)

    async def get_user_history(self, user_id: UUID, limit: int = 20) -> list[SearchHistory]:
        stmt = (
            select(SearchHistory)
            .where(SearchHistory.user_id == user_id)
            .limit(limit)
            .order_by(SearchHistory.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
