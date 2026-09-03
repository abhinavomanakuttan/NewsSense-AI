from uuid import UUID

from sqlalchemy import select

from app.models.user_preference import UserPreference
from app.repositories.base import BaseRepository


class UserPreferenceRepository(BaseRepository[UserPreference]):
    def __init__(self, db):
        super().__init__(db, UserPreference)

    async def get_by_user_id(self, user_id: UUID) -> UserPreference | None:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: UUID) -> UserPreference:
        existing = await self.get_by_user_id(user_id)
        if existing:
            return existing
        return await self.create(user_id=user_id)

    async def list_notification_enabled(self) -> list[UserPreference]:
        stmt = select(UserPreference).where(UserPreference.notification_enabled.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
