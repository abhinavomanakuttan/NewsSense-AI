from sqlalchemy import Column, String

from app.db.base import Base, TimestampMixin, UUIDMixin


class Tag(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "tags"

    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
