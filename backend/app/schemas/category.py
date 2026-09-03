from uuid import UUID

from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None
    parent_id: str | None = None
    display_order: str = "0"

    class Config:
        from_attributes = True


class CategoryCreateRequest(BaseModel):
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None
    parent_id: str | None = None
    display_order: str = "0"
