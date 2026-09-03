"""Event Summarizer Service for NewsSense AI.

Orchestrates:
- Fetching full event clusters (all member articles)
- Passing context to EventSummarizerAgent
- Persisting structured multi-source summary into the database
- Streaming summaries to Redis Stream stream:news:summarized
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.summarizer import EventSummarizerAgent
from app.db.session import async_session_factory
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventSummaryLength, EventSummaryOutput

logger = logging.getLogger(__name__)

STREAM_NEWS_SUMMARIZED = "stream:news:summarized"


class EventSummarizerService:
    """Orchestration service for generating and persisting multi-document event summaries."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        event_repo: EventRepository | None = None,
        summarizer_agent: EventSummarizerAgent | None = None,
    ):
        self._owns_session = session is None
        self.session = session or async_session_factory()
        self.event_repo = event_repo or EventRepository(self.session)
        self.agent = summarizer_agent or EventSummarizerAgent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._owns_session:
            await self.session.close()

    async def summarize_event_by_id(
        self,
        event_id: UUID | str,
        length: EventSummaryLength = EventSummaryLength.STANDARD,
        force_regenerate: bool = False,
    ) -> EventSummaryOutput:
        """Generate a verified, multi-document factual summary for an event by ID."""
        event = await self.event_repo.get_with_articles(UUID(str(event_id)))
        if not event:
            raise ValueError(f"Event {event_id} not found")

        # Return cached structured summary if present and not forced
        if not force_regenerate and event.structured_summary:
            try:
                cached_data = json.loads(event.structured_summary)
                return EventSummaryOutput.model_validate(cached_data)
            except Exception as e:
                logger.debug("Failed to deserialize cached structured summary: %s", e)

        # Prepare articles payload
        articles_data = []
        for a in event.articles:
            articles_data.append({
                "id": str(a.id),
                "title": a.title,
                "content": a.content or a.summary or "",
                "summary": a.summary or "",
                "source_name": a.source.name if a.source else "News Source",
                "source_domain": a.source.domain if a.source else "",
                "published_at": a.published_at or a.created_at,
                "credibility_score": a.credibility_score,
                "is_syndicated": a.is_syndicated,
                "entities": a.entities,
            })

        timeline_items = []
        if event.timeline:
            try:
                timeline_items = json.loads(event.timeline)
            except Exception:
                timeline_items = []

        summary_output = await self.agent.summarize_event(
            event_id=str(event.id),
            event_title=event.title,
            category=event.category,
            articles=articles_data,
            timeline_items=timeline_items,
            length=length,
        )

        # Persist summary back to event
        event.summary = summary_output.summary
        event.structured_summary = summary_output.model_dump_json()
        await self.session.flush()
        if self._owns_session:
            await self.session.commit()

        # Publish to Redis Stream
        await self._publish_to_stream(summary_output)

        return summary_output

    async def _publish_to_stream(self, summary: EventSummaryOutput):
        try:
            from app.pipeline.queue.redis_stream_producer import RedisStreamProducer
            producer = RedisStreamProducer()
            client = await producer._get_client()

            payload = {
                "event_id": summary.event_id,
                "headline": summary.headline,
                "summary": summary.summary,
                "confidence": summary.confidence,
                "key_points_count": len(summary.key_points),
            }
            await client.xadd(STREAM_NEWS_SUMMARIZED, fields={"data": json.dumps(payload)}, maxlen=10000, approximate=True)
            await producer.close()
        except Exception as exc:
            logger.debug("Redis Stream publish skipped: %s", exc)
