from datetime import UTC, datetime, timedelta

from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsEventItem,
    AnalyticsEventList,
    AnalyticsOverview,
    CategoryStats,
    DailyCount,
    SentimentStats,
    SourceStats,
    UserActivityStats,
)


def _date_keys(days: int) -> list[str]:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return [(today - timedelta(days=i)).date().isoformat() for i in range(days - 1, -1, -1)]


def _since(days: int) -> datetime:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=days - 1)


class AnalyticsService:
    def __init__(self, analytics_repo: AnalyticsRepository):
        self.analytics_repo = analytics_repo

    async def get_overview(self) -> AnalyticsOverview:
        data = await self.analytics_repo.get_overview()
        return AnalyticsOverview(**data)

    async def get_activity(self, days: int = 14) -> list[UserActivityStats]:
        keys = _date_keys(days)
        since = _since(days)

        active_users: dict[str, set[str]] = {k: set() for k in keys}
        page_views: dict[str, int] = {k: 0 for k in keys}
        searches: dict[str, int] = {k: 0 for k in keys}
        bookmarks: dict[str, int] = {k: 0 for k in keys}

        for date, user_id in await self.analytics_repo.get_daily_reads(since):
            if date in active_users:
                active_users[date].add(str(user_id))
                page_views[date] += 1
        for date, user_id in await self.analytics_repo.get_daily_searches(since):
            if date in active_users:
                active_users[date].add(str(user_id))
                searches[date] += 1
        for date, user_id in await self.analytics_repo.get_daily_bookmarks(since):
            if date in active_users:
                active_users[date].add(str(user_id))
                bookmarks[date] += 1

        return [
            UserActivityStats(
                date=k,
                active_users=len(active_users[k]),
                page_views=page_views[k],
                searches=searches[k],
                bookmarks=bookmarks[k],
            )
            for k in keys
        ]

    async def get_articles_trend(self, days: int = 14) -> list[DailyCount]:
        counts = dict(await self.analytics_repo.get_articles_trend(_since(days)))
        return [DailyCount(date=k, count=counts.get(k, 0)) for k in _date_keys(days)]

    async def get_categories(self, limit: int = 20) -> list[CategoryStats]:
        rows = await self.analytics_repo.get_category_distribution(limit)
        return [CategoryStats(category=name, article_count=count) for name, count in rows if count]

    async def get_sources(self, limit: int = 10) -> list[SourceStats]:
        rows = await self.analytics_repo.get_source_stats(limit)
        return [
            SourceStats(source=name, article_count=count, avg_credibility=round(cred, 3))
            for name, count, cred in rows
            if count
        ]

    async def get_sentiment(self) -> list[SentimentStats]:
        rows = await self.analytics_repo.get_sentiment_distribution()
        return [
            SentimentStats(sentiment=sentiment or "unknown", count=count)
            for sentiment, count in rows
        ]

    async def get_events(self, skip: int = 0, limit: int = 50) -> AnalyticsEventList:
        events, total = await self.analytics_repo.list_events(skip, limit)
        return AnalyticsEventList(
            events=[
                AnalyticsEventItem(
                    id=str(e.id),
                    event_type=e.event_type,
                    user_id=e.user_id,
                    article_id=e.article_id,
                    value=e.value,
                    timestamp=e.timestamp,
                    metadata=e.event_metadata or {},
                )
                for e in events
            ],
            total=total,
        )

    async def track_event(
        self,
        event_type: str,
        user_id: str | None = None,
        article_id: str | None = None,
        value: float | None = None,
        metadata: dict | None = None,
    ) -> AnalyticsEventItem:
        event = await self.analytics_repo.record_event(
            event_type=event_type,
            user_id=user_id,
            article_id=article_id,
            value=value,
            metadata=metadata,
        )
        return AnalyticsEventItem(
            id=str(event.id),
            event_type=event.event_type,
            user_id=event.user_id,
            article_id=event.article_id,
            value=event.value,
            timestamp=event.timestamp,
            metadata=event.event_metadata or {},
        )
