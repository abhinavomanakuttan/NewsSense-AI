from sqlalchemy import JSON, Column, DateTime, Float, String

from app.db.base import Base, TimestampMixin, UUIDMixin


class AnalyticsEvent(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "analytics_events"

    event_type = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=True)
    article_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)
    event_metadata = Column("metadata", JSON, default=dict, nullable=True)
    value = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
