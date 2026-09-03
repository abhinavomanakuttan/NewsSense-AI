from fastapi import APIRouter, Depends

from app.core.dependencies import get_tag_repo
from app.repositories.tag_repository import TagRepository
from app.schemas.tag import TagCreateRequest, TagResponse
from app.services.tag_service import TagService

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get("", response_model=list[TagResponse])
async def list_tags(
    tag_repo: TagRepository = Depends(get_tag_repo),
):
    service = TagService(tag_repo)
    return await service.get_tags()


@router.post("", response_model=TagResponse, status_code=201)
async def create_tag(
    request: TagCreateRequest,
    tag_repo: TagRepository = Depends(get_tag_repo),
):
    service = TagService(tag_repo)
    return await service.create_tag(request)
