from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import (
    get_article_repo,
    get_current_user,
    get_reading_history_repo,
)
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.schemas.reading_history import (
    ReadingHistoryCreateRequest,
    ReadingHistoryListResponse,
    ReadingHistoryResponse,
)
from app.services.reading_history_service import ReadingHistoryService

router = APIRouter(prefix="/reading-history", tags=["Reading History"])


@router.get("", response_model=ReadingHistoryListResponse)
async def list_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    history_repo: ReadingHistoryRepository = Depends(get_reading_history_repo),
):
    service = ReadingHistoryService(history_repo)
    return await service.get_history(current_user.id, skip, limit)


@router.post("", response_model=ReadingHistoryResponse, status_code=201)
async def record_reading(
    request: ReadingHistoryCreateRequest,
    current_user: User = Depends(get_current_user),
    history_repo: ReadingHistoryRepository = Depends(get_reading_history_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = ReadingHistoryService(history_repo, article_repo)
    return await service.record_reading(current_user.id, request)


@router.delete("", status_code=204)
async def clear_history(
    current_user: User = Depends(get_current_user),
    history_repo: ReadingHistoryRepository = Depends(get_reading_history_repo),
):
    service = ReadingHistoryService(history_repo)
    await service.clear_history(current_user.id)


@router.delete("/{history_id}", status_code=204)
async def remove_history_record(
    history_id: UUID,
    current_user: User = Depends(get_current_user),
    history_repo: ReadingHistoryRepository = Depends(get_reading_history_repo),
):
    service = ReadingHistoryService(history_repo)
    await service.remove_record(current_user.id, history_id)
