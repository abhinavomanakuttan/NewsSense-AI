from app.core.exceptions import DuplicateError
from app.repositories.tag_repository import TagRepository
from app.schemas.tag import TagCreateRequest, TagResponse


class TagService:
    def __init__(self, tag_repo: TagRepository):
        self.tag_repo = tag_repo

    async def get_tags(self) -> list[TagResponse]:
        tags = await self.tag_repo.get_all(order_by="name", descending=False)
        return [TagResponse.model_validate(t) for t in tags]

    async def create_tag(self, request: TagCreateRequest) -> TagResponse:
        existing = await self.tag_repo.get_by_slug(request.slug)
        if existing:
            raise DuplicateError("Tag with this slug already exists")
        tag = await self.tag_repo.create(**request.model_dump())
        return TagResponse.model_validate(tag)
