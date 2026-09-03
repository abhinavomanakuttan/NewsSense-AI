"""New-article notification producer.

After an article is enriched and classified, notify users whose saved
preferences match the article's category and who have notifications enabled.
Notifications are persisted and pushed in real time through the dispatcher.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.repositories.article_repository import ArticleRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.schemas.notification import NotificationResponse

logger = logging.getLogger(__name__)


class ArticleNotificationProducer:
    def __init__(
        self,
        session: AsyncSession | None = None,
        article_repo: ArticleRepository | None = None,
        notification_repo: NotificationRepository | None = None,
        preference_repo: UserPreferenceRepository | None = None,
    ):
        self._owns_session = session is None
        self.session = session or async_session_factory()
        self.article_repo = article_repo or ArticleRepository(self.session)
        self.notification_repo = notification_repo or NotificationRepository(self.session)
        self.preference_repo = preference_repo or UserPreferenceRepository(self.session)

    async def notify_for_article(self, article_id: UUID | str) -> int:
        """Create + push notifications for users interested in this article."""
        article = await self.article_repo.get_by_id(UUID(str(article_id)))
        if not article:
            return 0
        category = article.category
        if not category or not category.name:
            return 0

        category_name = category.name.lower()
        prefs = await self.preference_repo.list_notification_enabled()
        if not prefs:
            return 0

        created = 0
        for pref in prefs:
            preferred = {c.lower() for c in (pref.preferred_categories or [])}
            if preferred and category_name not in preferred:
                continue
            notification = await self.notification_repo.create(
                user_id=pref.user_id,
                title=f"New article: {article.title}",
                body=article.summary or f"A new article matching '{category.name}' was published.",
                notification_type="new_article",
                reference_id=str(article.id),
                reference_type="article",
            )
            await self._dispatch(notification)
            created += 1

        if self._owns_session:
            await self.session.commit()
        return created

    async def _dispatch(self, notification) -> None:
        try:
            from app.services.notification_dispatcher import notification_dispatcher

            payload = NotificationResponse.model_validate(notification).model_dump(mode="json")
            await notification_dispatcher.publish(str(notification.user_id), payload)
        except Exception as exc:
            logger.warning(f"Notification push failed for {notification.id}: {exc}")
