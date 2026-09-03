from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin, UUIDMixin


class SearchHistory(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "search_history"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query = Column(String(500), nullable=False)
    filters = Column(String(2000), nullable=True)
    result_count = Column(String(10), default="0", nullable=False)
