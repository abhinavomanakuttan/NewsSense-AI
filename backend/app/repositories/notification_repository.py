from uuid import UUID

from sqlalchemy import func, select

from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db):
        super().__init__(db, Notification)

    async def get_user_notifications(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(Notification.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_unread_count(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def mark_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        notification = result.scalar_one_or_none()
        if notification:
            notification.is_read = True
            await self.db.flush()
            return True
        return False

    async def mark_all_as_read(self, user_id: UUID) -> int:
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()
        for n in notifications:
            n.is_read = True
        await self.db.flush()
        return len(notifications)
