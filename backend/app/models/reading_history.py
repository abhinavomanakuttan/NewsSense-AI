from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ReadingHistory(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "reading_history"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id = Column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    read_duration_seconds = Column(Integer, default=0, nullable=False)
    scroll_depth = Column(Integer, default=0, nullable=False)

    article = relationship("Article", backref="reading_history_records")
