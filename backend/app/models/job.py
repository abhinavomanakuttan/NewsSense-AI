from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base, TimestampMixin, UUIDMixin


class Job(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "jobs"

    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(1000), nullable=False, unique=True)
    salary_range = Column(String(100), nullable=True)
    job_type = Column(String(50), nullable=True)
    industry = Column(String(100), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String(100), nullable=True)
