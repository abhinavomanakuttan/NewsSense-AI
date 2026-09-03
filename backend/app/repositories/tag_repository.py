from sqlalchemy import select

from app.models.tag import Tag
from app.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    def __init__(self, db):
        super().__init__(db, Tag)

    async def get_by_slug(self, slug: str) -> Tag | None:
        stmt = select(Tag).where(Tag.slug == slug)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, name: str, slug: str) -> Tag:
        existing = await self.get_by_slug(slug)
        if existing:
            return existing
        return await self.create(name=name, slug=slug)
