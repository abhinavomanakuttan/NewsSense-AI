from uuid import UUID

from pydantic import BaseModel


class TagResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    class Config:
        from_attributes = True


class TagCreateRequest(BaseModel):
    name: str
    slug: str
