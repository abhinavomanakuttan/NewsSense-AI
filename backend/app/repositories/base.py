from typing import TypeVar
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository[ModelType: Base]:
    def __init__(self, db: AsyncSession, model: type[ModelType]):
        self.db = db
        self.model = model

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def get_by_id(self, id: UUID) -> ModelType | None:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        descending: bool = True,
    ) -> list[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        if order_by and hasattr(self.model, order_by):
            col = getattr(self.model, order_by)
            stmt = stmt.order_by(col.desc() if descending else col.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: dict | None = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def update(self, id: UUID, **kwargs) -> ModelType | None:
        instance = await self.get_by_id(id)
        if not instance:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key) and value is not None:
                setattr(instance, key, value)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def delete(self, id: UUID) -> bool:
        stmt = sa_delete(self.model).where(self.model.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def exists(self, **kwargs) -> bool:
        stmt = select(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        stmt = stmt.limit(1)
        result = await self.db.execute(stmt)
        return result.first() is not None
