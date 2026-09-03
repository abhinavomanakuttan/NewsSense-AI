from uuid import UUID

from app.core.exceptions import NotFoundError
from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.schemas.article import ArticleListResponse, ArticleResponse


class ArticleService:
    def __init__(
        self,
        article_repo: ArticleRepository,
        bookmark_repo: BookmarkRepository | None = None,
        reading_history_repo: ReadingHistoryRepository | None = None,
    ):
        self.article_repo = article_repo
        self.bookmark_repo = bookmark_repo
        self.reading_history_repo = reading_history_repo

    async def get_article(self, slug: str) -> ArticleResponse:
        article = await self.article_repo.get_by_slug(slug)
        if not article:
            raise NotFoundError("Article not found")

        article.view_count = str(int(article.view_count) + 1)
        await self.article_repo.db.flush()

        return ArticleResponse.model_validate(article)

    async def get_articles(
        self, skip: int = 0, limit: int = 20, category: str | None = None
    ) -> list[ArticleListResponse]:
        if category:
            articles = await self.article_repo.get_by_category(UUID(category), skip, limit)
        else:
            articles = await self.article_repo.get_all(skip, limit, "published_at", True)

        return [ArticleListResponse.model_validate(a) for a in articles]

    async def get_trending(self, limit: int = 20) -> list[ArticleListResponse]:
        articles = await self.article_repo.get_trending(limit)
        return [ArticleListResponse.model_validate(a) for a in articles]
