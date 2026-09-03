from fastapi import APIRouter, Depends

from app.core.dependencies import get_category_repo
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreateRequest, CategoryResponse
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    category_repo: CategoryRepository = Depends(get_category_repo),
):
    service = CategoryService(category_repo)
    return await service.get_categories()


@router.get("/{slug}", response_model=CategoryResponse)
async def get_category(
    slug: str,
    category_repo: CategoryRepository = Depends(get_category_repo),
):
    service = CategoryService(category_repo)
    return await service.get_category(slug)


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    request: CategoryCreateRequest,
    category_repo: CategoryRepository = Depends(get_category_repo),
):
    service = CategoryService(category_repo)
    return await service.create_category(request)
