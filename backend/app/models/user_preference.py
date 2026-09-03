from sqlalchemy import JSON, Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin, UUIDMixin


class UserPreference(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "user_preferences"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    preferred_categories = Column(JSON, default=list, nullable=True)
    preferred_sources = Column(JSON, default=list, nullable=True)
    preferred_languages = Column(JSON, default=["en"], nullable=True)
    preferred_regions = Column(JSON, default=list, nullable=True)
    notification_enabled = Column(Boolean, default=True, nullable=False)
    dark_mode = Column(Boolean, default=False, nullable=False)
    email_digest_frequency = Column(String(20), default="daily", nullable=False)
    custom_settings = Column(JSON, default=dict, nullable=True)
