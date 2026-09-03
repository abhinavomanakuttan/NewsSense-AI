from uuid import UUID

from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    summary: str | None = None
    source_name: str | None = None
    category_name: str | None = None
    image_url: str | None = None
    published_at: str | None = None
    reason: str | None = None
    score: float = 0.0

    class Config:
        from_attributes = True
