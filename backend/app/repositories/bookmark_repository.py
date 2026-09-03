from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import joinedload

from app.models.article import Article
from app.models.bookmark import Bookmark
from app.repositories.base import BaseRepository


class BookmarkRepository(BaseRepository[Bookmark]):
    def __init__(self, db):
        super().__init__(db, Bookmark)

    async def get_user_bookmarks(
        self, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> list[Bookmark]:
        stmt = (
            select(Bookmark)
            .options(
                joinedload(Bookmark.article).joinedload(Article.source),
                joinedload(Bookmark.article).joinedload(Article.category),
            )
            .where(Bookmark.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(Bookmark.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def is_bookmarked(self, user_id: UUID, article_id: UUID) -> bool:
        stmt = select(Bookmark).where(
            and_(Bookmark.user_id == user_id, Bookmark.article_id == article_id)
        )
        result = await self.db.execute(stmt)
        return result.first() is not None

    async def remove_bookmark(self, user_id: UUID, article_id: UUID) -> bool:
        stmt = delete(Bookmark).where(
            and_(Bookmark.user_id == user_id, Bookmark.article_id == article_id)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def count_user_bookmarks(self, user_id: UUID) -> int:
        stmt = select(Bookmark).where(Bookmark.user_id == user_id)
        result = await self.db.execute(stmt)
        return len(result.scalars().all())
