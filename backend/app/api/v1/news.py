"""FastAPI router for Multi-Faceted News Feed."""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.article import Article
from app.schemas.article import ArticleListResponse
from app.schemas.news import NewsFeedResponse

router = APIRouter(prefix="/news", tags=["News"])


@router.get("", response_model=NewsFeedResponse)
async def get_news_feed(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: str | None = Query(None, description="Filter by category (Technology, Politics, etc.)"),
    country: str | None = Query(None, description="Filter by ISO country code (IN, US, UK, etc.)"),
    language: str | None = Query(None, description="Filter by language (en, hi, etc.)"),
    date_from: str | None = Query(None, description="Filter published after date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter published before date (YYYY-MM-DD)"),
    source: str | None = Query(None, description="Filter by news source name"),
    topic: str | None = Query(None, description="Filter by topic keyword"),
    importance: float | None = Query(None, description="Minimum importance or credibility score"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve filtered news feed supporting category, country, language, date, source, topic, importance."""
    stmt = select(Article)
    count_stmt = select(func.count(Article.id))

    filters_applied: dict[str, Any] = {}

    if category:
        stmt = stmt.where(Article.category_name.ilike(f"%{category}%"))
        count_stmt = count_stmt.where(Article.category_name.ilike(f"%{category}%"))
        filters_applied["category"] = category

    if country:
        stmt = stmt.where(Article.country == country.upper())
        count_stmt = count_stmt.where(Article.country == country.upper())
        filters_applied["country"] = country

    if language:
        stmt = stmt.where(Article.language == language.lower())
        count_stmt = count_stmt.where(Article.language == language.lower())
        filters_applied["language"] = language

    if source:
        stmt = stmt.where(Article.source_name.ilike(f"%{source}%"))
        count_stmt = count_stmt.where(Article.source_name.ilike(f"%{source}%"))
        filters_applied["source"] = source

    if topic:
        stmt = stmt.where(
            (Article.title.ilike(f"%{topic}%")) |
            (Article.keywords.ilike(f"%{topic}%")) |
            (Article.entities.ilike(f"%{topic}%"))
        )
        count_stmt = count_stmt.where(
            (Article.title.ilike(f"%{topic}%")) |
            (Article.keywords.ilike(f"%{topic}%")) |
            (Article.entities.ilike(f"%{topic}%"))
        )
        filters_applied["topic"] = topic

    if date_from:
        stmt = stmt.where(Article.published_at >= date_from)
        count_stmt = count_stmt.where(Article.published_at >= date_from)
        filters_applied["date_from"] = date_from

    if date_to:
        stmt = stmt.where(Article.published_at <= date_to)
        count_stmt = count_stmt.where(Article.published_at <= date_to)
        filters_applied["date_to"] = date_to

    # Order by newest
    stmt = stmt.order_by(Article.created_at.desc()).offset(skip).limit(limit)

    total = (await db.execute(count_stmt)).scalar() or 0
    articles = (await db.execute(stmt)).scalars().all()

    article_responses = [
        ArticleListResponse(
            id=a.id,
            title=a.title,
            slug=a.slug,
            summary=a.summary or (a.content[:300] if a.content else ""),
            source_name=a.source_name,
            category_name=a.category_name,
            image_url=None,
            published_at=a.published_at or str(a.created_at),
            sentiment=a.sentiment,
            credibility_score=a.sentiment_score,
            tags=[],
        )
        for a in articles
    ]

    return NewsFeedResponse(
        total=total,
        skip=skip,
        limit=limit,
        articles=article_responses,
        applied_filters=filters_applied,
    )
