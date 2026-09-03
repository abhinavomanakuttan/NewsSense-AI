from sqlalchemy import JSON, Boolean, Column, String

from app.db.base import Base, TimestampMixin, UUIDMixin


class User(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(20), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    preferences = Column(JSON, default=dict, nullable=True)
