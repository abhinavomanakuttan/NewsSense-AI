from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id, get_current_user_role
from app.db.session import get_session
from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.event_repository import EventRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.repositories.search_history_repository import SearchHistoryRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository

oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
):
    """Return the current user when a valid token is provided, otherwise None.

    Used by endpoints that work for both anonymous and authenticated visitors
    (e.g. search), where the authenticated user simply gets extra tracking.
    """
    if not token:
        return None
    try:
        from app.core.security import decode_token

        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        repo = UserRepository(db)
        return await repo.get_by_id(UUID(user_id))
    except HTTPException:
        return None


async def get_current_admin(
    user=Depends(get_current_user),
    role: str = Depends(get_current_user_role),
):
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


get_current_admin_user = get_current_admin


def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_article_repo(db: AsyncSession = Depends(get_db)) -> ArticleRepository:
    return ArticleRepository(db)


def get_source_repo(db: AsyncSession = Depends(get_db)) -> SourceRepository:
    return SourceRepository(db)


def get_category_repo(db: AsyncSession = Depends(get_db)) -> CategoryRepository:
    return CategoryRepository(db)


def get_tag_repo(db: AsyncSession = Depends(get_db)) -> TagRepository:
    return TagRepository(db)


def get_event_repo(db: AsyncSession = Depends(get_db)) -> EventRepository:
    return EventRepository(db)


def get_bookmark_repo(db: AsyncSession = Depends(get_db)) -> BookmarkRepository:
    return BookmarkRepository(db)


def get_notification_repo(db: AsyncSession = Depends(get_db)) -> NotificationRepository:
    return NotificationRepository(db)


def get_user_preference_repo(db: AsyncSession = Depends(get_db)) -> UserPreferenceRepository:
    return UserPreferenceRepository(db)


def get_search_history_repo(db: AsyncSession = Depends(get_db)) -> SearchHistoryRepository:
    return SearchHistoryRepository(db)


def get_reading_history_repo(db: AsyncSession = Depends(get_db)) -> ReadingHistoryRepository:
    return ReadingHistoryRepository(db)


def get_conversation_repo(db: AsyncSession = Depends(get_db)) -> ConversationRepository:
    return ConversationRepository(db)
