from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    title: str
    body: str | None = None
    notification_type: str
    reference_id: str | None = None
    reference_type: str | None = None
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
