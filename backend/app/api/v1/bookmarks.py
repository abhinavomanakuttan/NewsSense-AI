from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_article_repo, get_bookmark_repo, get_current_user
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.schemas.bookmark import BookmarkCreateRequest, BookmarkResponse
from app.services.bookmark_service import BookmarkService

router = APIRouter(prefix="/bookmarks", tags=["Bookmarks"])


@router.get("", response_model=list[BookmarkResponse])
async def list_bookmarks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    bookmark_repo: BookmarkRepository = Depends(get_bookmark_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = BookmarkService(bookmark_repo, article_repo)
    return await service.get_bookmarks(current_user.id, skip, limit)


@router.post("", response_model=BookmarkResponse, status_code=201)
async def add_bookmark(
    request: BookmarkCreateRequest,
    current_user: User = Depends(get_current_user),
    bookmark_repo: BookmarkRepository = Depends(get_bookmark_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = BookmarkService(bookmark_repo, article_repo)
    return await service.add_bookmark(current_user.id, request.article_id)


@router.delete("/{article_id}", status_code=204)
async def remove_bookmark(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    bookmark_repo: BookmarkRepository = Depends(get_bookmark_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = BookmarkService(bookmark_repo, article_repo)
    await service.remove_bookmark(current_user.id, article_id)
