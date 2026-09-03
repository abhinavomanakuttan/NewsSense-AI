from sqlalchemy import select

from app.models.source import Source
from app.repositories.base import BaseRepository


class SourceRepository(BaseRepository[Source]):
    def __init__(self, db):
        super().__init__(db, Source)

    async def get_by_url(self, url: str) -> Source | None:
        stmt = select(Source).where(Source.url == url)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_sources(self) -> list[Source]:
        stmt = select(Source).where(Source.is_active)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
