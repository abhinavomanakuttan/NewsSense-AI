from uuid import UUID

from app.core.exceptions import DuplicateError, NotFoundError
from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.schemas.bookmark import BookmarkResponse
from app.services.recommendation_service import invalidate_user_recommendations


class BookmarkService:
    def __init__(self, bookmark_repo: BookmarkRepository, article_repo: ArticleRepository):
        self.bookmark_repo = bookmark_repo
        self.article_repo = article_repo

    async def add_bookmark(self, user_id: UUID, article_id: UUID) -> BookmarkResponse:
        article = await self.article_repo.get_by_id(article_id)
        if not article:
            raise NotFoundError("Article not found")

        if await self.bookmark_repo.is_bookmarked(user_id, article_id):
            raise DuplicateError("Article already bookmarked")

        bookmark = await self.bookmark_repo.create(user_id=user_id, article_id=article_id)
        await invalidate_user_recommendations(user_id)
        return BookmarkResponse.model_validate(bookmark)

    async def remove_bookmark(self, user_id: UUID, article_id: UUID) -> None:
        if not await self.bookmark_repo.remove_bookmark(user_id, article_id):
            raise NotFoundError("Bookmark not found")
        await invalidate_user_recommendations(user_id)

    async def get_bookmarks(
        self, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> list[BookmarkResponse]:
        bookmarks = await self.bookmark_repo.get_user_bookmarks(user_id, skip, limit)
        return [BookmarkResponse.model_validate(b) for b in bookmarks]
