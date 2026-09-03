from sqlalchemy import Boolean, Column, Float, Integer, String, Text

from app.db.base import Base, TimestampMixin, UUIDMixin


class Source(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "sources"

    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    domain = Column(String(255), nullable=True)
    feed_url = Column(String(500), nullable=True)
    api_endpoint = Column(String(500), nullable=True)
    source_type = Column(String(50), nullable=False)  # rss, api, scraper
    language = Column(String(10), default="en", nullable=False)
    country = Column(String(5), nullable=True)
    category = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    reliability_score = Column(Float, default=0.5, nullable=False)
    fetch_interval_minutes = Column(Integer, default=15, nullable=False)
    rate_limit = Column(Integer, default=60, nullable=False)  # requests per hour
    priority = Column(String(20), default="normal", nullable=False)  # high, normal, low
    last_fetched_at = Column(String(50), nullable=True)
    last_fetch_success = Column(Boolean, nullable=True)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    config = Column(Text, nullable=True)  # JSON: api keys, extra params

    # Canonical attribute property aliases
    @property
    def source_id(self):
        return self.id

    @property
    def rss_url(self):
        return self.feed_url

    @rss_url.setter
    def rss_url(self, value):
        self.feed_url = value

    @property
    def active(self):
        return self.is_active

    @active.setter
    def active(self, value):
        self.is_active = value

    @property
    def last_fetched(self):
        return self.last_fetched_at

    @last_fetched.setter
    def last_fetched(self, value):
        self.last_fetched_at = value

    # Backward compatibility alias
    @property
    def reputation_score(self):
        return self.reliability_score

    @reputation_score.setter
    def reputation_score(self, value):
        self.reliability_score = value

