from sqlalchemy import select

from app.models.category import Category
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, db):
        super().__init__(db, Category)

    async def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
