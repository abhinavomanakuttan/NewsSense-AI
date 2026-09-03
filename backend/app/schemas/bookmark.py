from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator


class BookmarkResponse(BaseModel):
    id: UUID
    user_id: UUID
    article_id: UUID
    created_at: datetime
    title: str | None = None
    slug: str | None = None
    url: str | None = None
    summary: str | None = None
    image_url: str | None = None
    source_name: str | None = None
    published_at: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_orm(cls, value):
        if isinstance(value, dict):
            return value
        article = getattr(value, "article", None)
        return {
            "id": value.id,
            "user_id": value.user_id,
            "article_id": value.article_id,
            "created_at": value.created_at,
            "title": article.title if article else None,
            "slug": article.slug if article else None,
            "url": article.url if article else None,
            "summary": article.summary if article else None,
            "image_url": article.image_url if article else None,
            "source_name": article.source.name if article and article.source else None,
            "published_at": article.published_at if article else None,
        }


class BookmarkCreateRequest(BaseModel):
    article_id: UUID
