from uuid import UUID

from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationListResponse, NotificationResponse


class NotificationService:
    def __init__(self, notification_repo: NotificationRepository):
        self.notification_repo = notification_repo

    async def get_notifications(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> NotificationListResponse:
        notifications = await self.notification_repo.get_user_notifications(user_id, skip, limit)
        unread_count = await self.notification_repo.get_unread_count(user_id)

        return NotificationListResponse(
            notifications=[NotificationResponse.model_validate(n) for n in notifications],
            unread_count=unread_count,
        )

    async def mark_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        return await self.notification_repo.mark_as_read(notification_id, user_id)

    async def mark_all_as_read(self, user_id: UUID) -> int:
        return await self.notification_repo.mark_all_as_read(user_id)

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        body: str,
        notification_type: str,
        reference_id: str = None,
        reference_type: str = None,
    ):
        notification = await self.notification_repo.create(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        await self._dispatch(notification)
        return notification

    async def _dispatch(self, notification) -> None:
        """Push a freshly created notification to the user's live sockets."""
        try:
            from app.services.notification_dispatcher import notification_dispatcher

            payload = NotificationResponse.model_validate(notification).model_dump(mode="json")
            await notification_dispatcher.publish(str(notification.user_id), payload)
        except Exception:
            # Push is best-effort; the notification remains in the DB.
            pass
