from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base, TimestampMixin, UUIDMixin


class Sport(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "sports"

    title = Column(String(500), nullable=False)
    sport_type = Column(String(50), nullable=False, index=True)
    league = Column(String(100), nullable=True)
    team1 = Column(String(255), nullable=True)
    team2 = Column(String(255), nullable=True)
    score = Column(String(50), nullable=True)
    status = Column(String(50), default="upcoming", nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=True)
    summary = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True)
    source = Column(String(100), nullable=True)
