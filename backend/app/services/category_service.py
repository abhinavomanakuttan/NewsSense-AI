from app.core.exceptions import DuplicateError, NotFoundError
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreateRequest, CategoryResponse


class CategoryService:
    def __init__(self, category_repo: CategoryRepository):
        self.category_repo = category_repo

    async def get_categories(self) -> list[CategoryResponse]:
        categories = await self.category_repo.get_all(order_by="display_order", descending=False)
        return [CategoryResponse.model_validate(c) for c in categories]

    async def get_category(self, slug: str) -> CategoryResponse:
        category = await self.category_repo.get_by_slug(slug)
        if not category:
            raise NotFoundError("Category not found")
        return CategoryResponse.model_validate(category)

    async def create_category(self, request: CategoryCreateRequest) -> CategoryResponse:
        existing = await self.category_repo.get_by_slug(request.slug)
        if existing:
            raise DuplicateError("Category with this slug already exists")
        category = await self.category_repo.create(**request.model_dump())
        return CategoryResponse.model_validate(category)
