from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin, UUIDMixin


class Notification(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "notifications"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(500), nullable=False)
    body = Column(String(2000), nullable=True)
    notification_type = Column(String(50), nullable=False)
    reference_id = Column(String(100), nullable=True)
    reference_type = Column(String(50), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    is_sent = Column(Boolean, default=False, nullable=False)
