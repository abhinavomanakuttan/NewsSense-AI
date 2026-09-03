import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.models.article import Article
from app.models.event import Event
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    def __init__(self, db):
        super().__init__(db, Event)

    async def get_by_slug(self, slug: str) -> Event | None:
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_events(self, limit: int = 20) -> list[Event]:
        stmt = (
            select(Event)
            .where(Event.is_active)
            .order_by(Event.importance_score.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_events_in_window(self, hours: int = 72, limit: int = 200) -> list[Event]:
        """Fetch active events within sliding temporal window (default last 72 hours)."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        stmt = (
            select(Event)
            .where(Event.is_active)
            .where((Event.end_date >= cutoff) | (Event.created_at >= cutoff) | (Event.end_date.is_(None)))
            .order_by(desc(Event.end_date))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_with_articles(self, event_id: UUID) -> Event | None:
        stmt = (
            select(Event)
            .options(selectinload(Event.articles))
            .where(Event.id == event_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
