from sqlalchemy import Column, String, Text

from app.db.base import Base, TimestampMixin, UUIDMixin


class Category(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "categories"

    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    parent_id = Column(String(50), nullable=True)
    display_order = Column(String(10), default="0", nullable=False)
