from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models.analytics import AnalyticsEvent
from app.models.article import Article
from app.models.bookmark import Bookmark
from app.models.category import Category
from app.models.event import Event
from app.models.reading_history import ReadingHistory
from app.models.search_history import SearchHistory
from app.models.source import Source
from app.models.user import User
from app.repositories.base import BaseRepository


class AnalyticsRepository(BaseRepository[AnalyticsEvent]):
    def __init__(self, db):
        super().__init__(db, AnalyticsEvent)

    async def get_overview(self) -> dict:
        total_users = await self.db.execute(select(func.count(User.id)))
        total_articles = await self.db.execute(select(func.count(Article.id)))
        total_sources = await self.db.execute(select(func.count(Source.id)))
        active_sources = await self.db.execute(
            select(func.count(Source.id)).where(Source.is_active)
        )
        total_searches = await self.db.execute(select(func.count(SearchHistory.id)))
        total_events = await self.db.execute(select(func.count(Event.id)))

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        articles_today = await self.db.execute(
            select(func.count(Article.id)).where(Article.created_at >= today_start)
        )

        active_since = datetime.now(UTC) - timedelta(days=1)
        active_users_today = await self.db.execute(
            select(func.count()).select_from(Bookmark).where(Bookmark.created_at >= active_since)
        )
        active_users = await self.db.execute(
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(AnalyticsEvent.timestamp >= active_since)
        )
        active_users_count = max(
            active_users_today.scalar() or 0,
            active_users.scalar() or 0,
        )

        return {
            "total_users": total_users.scalar() or 0,
            "active_users_today": active_users_count,
            "total_articles": total_articles.scalar() or 0,
            "articles_today": articles_today.scalar() or 0,
            "total_sources": total_sources.scalar() or 0,
            "active_sources": active_sources.scalar() or 0,
            "total_searches": total_searches.scalar() or 0,
            "total_events": total_events.scalar() or 0,
        }

    async def get_daily_reads(self, since: datetime) -> list[tuple[str, str]]:
        stmt = select(func.date(ReadingHistory.created_at), ReadingHistory.user_id).where(
            ReadingHistory.created_at >= since
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_daily_searches(self, since: datetime) -> list[tuple[str, str]]:
        stmt = select(func.date(SearchHistory.created_at), SearchHistory.user_id).where(
            SearchHistory.created_at >= since
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_daily_bookmarks(self, since: datetime) -> list[tuple[str, str]]:
        stmt = select(func.date(Bookmark.created_at), Bookmark.user_id).where(
            Bookmark.created_at >= since
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_articles_trend(self, since: datetime) -> list[tuple[str, int]]:
        stmt = (
            select(func.date(Article.created_at), func.count(Article.id))
            .where(Article.created_at >= since)
            .group_by(func.date(Article.created_at))
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_category_distribution(self, limit: int = 20) -> list[tuple[str | None, int]]:
        stmt = (
            select(Category.name, func.count(Article.id))
            .outerjoin(Article, Article.category_id == Category.id)
            .group_by(Category.name)
            .order_by(func.count(Article.id).desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_source_stats(self, limit: int = 10) -> list[tuple[str, int, float]]:
        stmt = (
            select(
                Source.name,
                func.count(Article.id),
                func.coalesce(func.avg(Article.credibility_score), 0.0),
            )
            .outerjoin(Article, Article.source_id == Source.id)
            .group_by(Source.name)
            .order_by(func.count(Article.id).desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1], float(row[2] or 0.0)) for row in result.all()]

    async def get_sentiment_distribution(self) -> list[tuple[str | None, int]]:
        stmt = (
            select(Article.sentiment, func.count(Article.id))
            .where(Article.sentiment.is_not(None))
            .group_by(Article.sentiment)
            .order_by(func.count(Article.id).desc())
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def list_events(self, skip: int = 0, limit: int = 50) -> tuple[list[AnalyticsEvent], int]:
        total_stmt = select(func.count(AnalyticsEvent.id))
        total = (await self.db.execute(total_stmt)).scalar() or 0
        stmt = (
            select(AnalyticsEvent)
            .order_by(AnalyticsEvent.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def record_event(
        self,
        event_type: str,
        user_id: str | None = None,
        article_id: str | None = None,
        session_id: str | None = None,
        metadata: dict | None = None,
        value: float | None = None,
    ) -> AnalyticsEvent:
        return await self.create(
            event_type=event_type,
            user_id=user_id,
            article_id=article_id,
            session_id=session_id,
            event_metadata=metadata or {},
            value=value,
            timestamp=datetime.now(UTC),
        )
