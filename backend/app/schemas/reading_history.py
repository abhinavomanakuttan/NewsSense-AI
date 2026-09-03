from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReadingHistoryResponse(BaseModel):
    id: UUID
    article_id: UUID
    read_duration_seconds: int = 0
    scroll_depth: int = 0
    created_at: datetime
    title: str | None = None
    slug: str | None = None
    url: str | None = None
    summary: str | None = None
    source_name: str | None = None
    image_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_orm(cls, value):
        if isinstance(value, dict):
            return value
        article = getattr(value, "article", None)
        return {
            "id": value.id,
            "article_id": value.article_id,
            "read_duration_seconds": value.read_duration_seconds,
            "scroll_depth": value.scroll_depth,
            "created_at": value.created_at,
            "title": article.title if article else None,
            "slug": article.slug if article else None,
            "url": article.url if article else None,
            "summary": article.summary if article else None,
            "source_name": article.source.name if article and article.source else None,
            "image_url": article.image_url if article else None,
        }


class ReadingHistoryCreateRequest(BaseModel):
    article_id: UUID
    read_duration_seconds: int = Field(0, ge=0)
    scroll_depth: int = Field(0, ge=0)


class ReadingHistoryListResponse(BaseModel):
    items: list[ReadingHistoryResponse]
    total: int
