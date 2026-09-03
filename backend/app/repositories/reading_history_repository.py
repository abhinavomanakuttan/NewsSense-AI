from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import joinedload

from app.models.article import Article
from app.models.reading_history import ReadingHistory
from app.repositories.base import BaseRepository


class ReadingHistoryRepository(BaseRepository[ReadingHistory]):
    def __init__(self, db):
        super().__init__(db, ReadingHistory)

    async def get_user_history(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[ReadingHistory]:
        stmt = (
            select(ReadingHistory)
            .where(ReadingHistory.user_id == user_id)
            .options(
                joinedload(ReadingHistory.article).joinedload(Article.source),
                joinedload(ReadingHistory.article).joinedload(Article.category),
            )
            .offset(skip)
            .limit(limit)
            .order_by(ReadingHistory.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_user_and_article(self, user_id: UUID, article_id: UUID):
        stmt = select(ReadingHistory).where(
            and_(ReadingHistory.user_id == user_id, ReadingHistory.article_id == article_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def count_user_history(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ReadingHistory)
            .where(ReadingHistory.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def remove_user_record(self, user_id: UUID, history_id: UUID) -> bool:
        stmt = delete(ReadingHistory).where(
            and_(ReadingHistory.id == history_id, ReadingHistory.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
