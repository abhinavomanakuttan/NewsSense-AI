from uuid import UUID

from app.core.exceptions import NotFoundError
from app.repositories.article_repository import ArticleRepository
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventArticleResponse, EventResponse


class EventService:
    def __init__(self, event_repo: EventRepository, article_repo: ArticleRepository):
        self.event_repo = event_repo
        self.article_repo = article_repo

    async def get_event(self, slug: str) -> EventResponse:
        event = await self.event_repo.get_by_slug(slug)
        if not event:
            raise NotFoundError("Event not found")
        return EventResponse.model_validate(event)

    async def get_events(self, skip: int = 0, limit: int = 20) -> list[EventResponse]:
        events = await self.event_repo.get_active_events(limit)
        return [EventResponse.model_validate(e) for e in events]

    async def get_event_articles(self, event_id: UUID) -> list[EventArticleResponse]:
        articles = await self.article_repo.get_by_event_id(event_id)
        return [EventArticleResponse.model_validate(a) for a in articles]
