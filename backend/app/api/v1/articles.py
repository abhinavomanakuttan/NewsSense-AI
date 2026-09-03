from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_article_repo
from app.repositories.article_repository import ArticleRepository
from app.schemas.article import ArticleListResponse, ArticleResponse
from app.services.article_service import ArticleService

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("", response_model=list[ArticleListResponse])
async def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: str = Query(None),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = ArticleService(article_repo)
    return await service.get_articles(skip, limit, category)


@router.get("/trending", response_model=list[ArticleListResponse])
async def trending_articles(
    limit: int = Query(20, ge=1, le=50),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = ArticleService(article_repo)
    return await service.get_trending(limit)


@router.get("/{slug}", response_model=ArticleResponse)
async def get_article(
    slug: str,
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = ArticleService(article_repo)
    return await service.get_article(slug)
