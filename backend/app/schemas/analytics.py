from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsOverview(BaseModel):
    total_users: int
    active_users_today: int
    total_articles: int
    articles_today: int
    total_sources: int
    active_sources: int
    total_searches: int
    total_events: int


class TrendingTopic(BaseModel):
    topic: str
    article_count: int
    trend_score: float
    category: str | None = None


class UserActivityStats(BaseModel):
    date: str
    active_users: int
    page_views: int
    searches: int
    bookmarks: int


class DailyCount(BaseModel):
    date: str
    count: int


class CategoryStats(BaseModel):
    category: str | None
    article_count: int


class SourceStats(BaseModel):
    source: str
    article_count: int
    avg_credibility: float = 0.0


class SentimentStats(BaseModel):
    sentiment: str
    count: int


class AnalyticsEventItem(BaseModel):
    id: str
    event_type: str
    user_id: str | None = None
    article_id: str | None = None
    value: float | None = None
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyticsEventList(BaseModel):
    events: list[AnalyticsEventItem]
    total: int


class TrackEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    article_id: str | None = None
    value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
