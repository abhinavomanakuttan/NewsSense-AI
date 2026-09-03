from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_source_repo
from app.repositories.source_repository import SourceRepository
from app.schemas.source import SourceCreateRequest, SourceResponse, SourceUpdateRequest
from app.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    active: bool | None = Query(None),
    source_repo: SourceRepository = Depends(get_source_repo),
):
    service = SourceService(source_repo)
    return await service.get_sources(skip, limit, category, priority, active)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    service = SourceService(source_repo)
    return await service.get_source(source_id)


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    request: SourceCreateRequest,
    source_repo: SourceRepository = Depends(get_source_repo),
    user=Depends(get_current_user),
):
    service = SourceService(source_repo)
    return await service.create_source(request)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    request: SourceUpdateRequest,
    source_repo: SourceRepository = Depends(get_source_repo),
    user=Depends(get_current_user),
):
    service = SourceService(source_repo)
    return await service.update_source(source_id, request.model_dump(exclude_none=True))


@router.post("/{source_id}/toggle", response_model=SourceResponse)
async def toggle_source(
    source_id: UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
    user=Depends(get_current_user),
):
    service = SourceService(source_repo)
    return await service.toggle_active(source_id)


@router.post("/{source_id}/fetch")
async def fetch_source_now(
    source_id: UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
    user=Depends(get_current_user),
):
    service = SourceService(source_repo)
    return await service.trigger_fetch(source_id)


@router.get("/{source_id}/metrics")
async def get_source_metrics(
    source_id: UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    service = SourceService(source_repo)
    return await service.get_source_metrics(source_id)


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
    user=Depends(get_current_user),
):
    service = SourceService(source_repo)
    await service.delete_source(source_id)

