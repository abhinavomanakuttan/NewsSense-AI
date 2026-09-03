from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.models.article import Article
from app.models.category import Category
from app.models.source import Source
from app.repositories.base import BaseRepository

_ARTICLE_LOADS = (
    joinedload(Article.source),
    joinedload(Article.category),
    joinedload(Article.tags),
)


class ArticleRepository(BaseRepository[Article]):
    def __init__(self, db):
        super().__init__(db, Article)

    async def get_by_id(self, id: UUID) -> Article | None:
        stmt = select(Article).where(Article.id == id).options(*_ARTICLE_LOADS)
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Article | None:
        stmt = select(Article).where(Article.slug == slug).options(*_ARTICLE_LOADS)
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_url(self, url: str) -> Article | None:
        stmt = select(Article).where(Article.url == url)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_content_hash(self, content_hash: str) -> Article | None:
        stmt = select(Article).where(Article.content_hash == content_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_event_id(self, event_id: UUID, limit: int = 50) -> list[Article]:
        stmt = (
            select(Article)
            .where(Article.event_id == event_id)
            .options(*_ARTICLE_LOADS)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def search_by_keywords(
        self,
        query: str,
        skip: int = 0,
        limit: int = 20,
        filters: dict | None = None,
        sort_by: str = "relevance",
        sort_order: str = "desc",
    ) -> tuple[list[Article], int]:
        filters = filters or {}
        search_filter = or_(
            Article.title.ilike(f"%{query}%"),
            Article.summary.ilike(f"%{query}%"),
            Article.content.ilike(f"%{query}%"),
            Article.keywords.ilike(f"%{query}%"),
        )

        stmt = select(Article).where(search_filter).options(*_ARTICLE_LOADS)

        if filters.get("category"):
            stmt = stmt.join(Article.category).filter(Category.name == filters["category"])
        if filters.get("source"):
            stmt = stmt.join(Article.source).filter(Source.name == filters["source"])
        if filters.get("language"):
            stmt = stmt.filter(Article.language == filters["language"])
        if filters.get("sentiment"):
            stmt = stmt.filter(Article.sentiment == filters["sentiment"])
        if filters.get("date_from"):
            stmt = stmt.filter(Article.published_at >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.filter(Article.published_at <= filters["date_to"])

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(total_stmt)
        total = total_result.scalar() or 0

        if sort_by == "date" and hasattr(Article, "published_at"):
            col = Article.published_at
        elif sort_by == "view_count":
            col = Article.view_count
        elif sort_by == "credibility" and hasattr(Article, "credibility_score"):
            col = Article.credibility_score
        else:
            col = Article.published_at

        stmt = stmt.order_by(col.desc() if sort_order == "desc" else col.asc())
        stmt = stmt.offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all()), total

    async def get_trending(self, limit: int = 20) -> list[Article]:
        stmt = (
            select(Article)
            .options(*_ARTICLE_LOADS)
            .order_by(Article.view_count.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_recommendation_candidates(
        self,
        limit: int = 50,
        excluded_ids: list[UUID] | None = None,
        languages: list[str] | None = None,
    ) -> list[Article]:
        """Recent articles eligible for recommendations.

        Excludes already-consumed articles (read/bookmarked) and, when
        `languages` is provided, only returns articles in those languages.
        """
        stmt = (
            select(Article)
            .options(*_ARTICLE_LOADS)
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
        if excluded_ids:
            stmt = stmt.where(Article.id.not_in(excluded_ids))
        if languages:
            stmt = stmt.where(Article.language.in_(languages))
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_category(
        self, category_id: UUID, skip: int = 0, limit: int = 20
    ) -> list[Article]:
        stmt = (
            select(Article)
            .where(Article.category_id == category_id)
            .options(*_ARTICLE_LOADS)
            .offset(skip)
            .limit(limit)
            .order_by(Article.published_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_source(self, source_id: UUID, skip: int = 0, limit: int = 20) -> list[Article]:
        stmt = (
            select(Article)
            .where(Article.source_id == source_id)
            .options(*_ARTICLE_LOADS)
            .offset(skip)
            .limit(limit)
            .order_by(Article.published_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        descending: bool = True,
    ) -> list[Article]:
        stmt = select(Article).options(*_ARTICLE_LOADS).offset(skip).limit(limit)
        if order_by and hasattr(Article, order_by):
            col = getattr(Article, order_by)
            stmt = stmt.order_by(col.desc() if descending else col.asc())
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def count_articles(self, filters: dict | None = None) -> int:
        stmt = select(func.count()).select_from(Article)
        if filters:
            for key, value in filters.items():
                if hasattr(Article, key):
                    stmt = stmt.where(getattr(Article, key) == value)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
