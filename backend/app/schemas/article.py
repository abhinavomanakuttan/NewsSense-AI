from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator


def _article_to_dict(article) -> dict:
    """Flatten an Article ORM object into the canonical dict shape."""
    source_name = (
        getattr(article, "source_name", None)
        or (article.source.name if getattr(article, "source", None) else None)
    )
    category_name = (
        getattr(article, "category_name", None)
        or (article.category.name if getattr(article, "category", None) else None)
    )
    data = {
        "id": article.id,
        "article_id": article.id,
        "title": article.title,
        "slug": article.slug,
        "url": article.url,
        "source_id": article.source_id,
        "source_name": source_name,
        "category_id": article.category_id,
        "category_name": category_name,
        "category": category_name,
        "event_id": article.event_id,
        "summary": article.summary,
        "description": article.summary,
        "content": article.content,
        "author": article.author,
        "published_at": article.published_at,
        "discovered_at": getattr(article, "discovered_at", None),
        "language": article.language or "en",
        "country": getattr(article, "country", None),
        "sentiment": article.sentiment,
        "sentiment_score": article.sentiment_score,
        "keywords": article.keywords,
        "entities": article.entities,
        "credibility_score": article.credibility_score,
        "credibility_factors": article.credibility_factors,
        "image_url": article.image_url,
        "view_count": article.view_count or "0",
        "is_verified": article.is_verified or False,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
        "tags": [tag.name for tag in article.tags] if getattr(article, "tags", None) else [],
        "raw_metadata": getattr(article, "raw_metadata", None),
        "normalized_title": getattr(article, "normalized_title", None),
        "content_hash": getattr(article, "content_hash", None),
        "url_hash": getattr(article, "url_hash", None),
        "source_hash": getattr(article, "source_hash", None),
        "article_fingerprint": getattr(article, "article_fingerprint", None),
    }
    return data


class ArticleResponse(BaseModel):
    id: UUID
    article_id: UUID | None = None
    title: str
    slug: str
    url: str
    source_id: UUID | None = None
    source_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    category: str | None = None
    event_id: UUID | None = None
    summary: str | None = None
    description: str | None = None
    content: str | None = None
    author: str | None = None
    published_at: str | None = None
    discovered_at: str | None = None
    language: str = "en"
    country: str | None = None
    sentiment: str | None = None
    sentiment_score: float | None = None
    keywords: str | None = None
    entities: str | None = None
    credibility_score: float | None = None
    credibility_factors: str | None = None
    image_url: str | None = None
    view_count: str = "0"
    is_verified: bool = False
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    raw_metadata: str | None = None
    normalized_title: str | None = None
    content_hash: str | None = None
    url_hash: str | None = None
    source_hash: str | None = None
    article_fingerprint: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_orm(cls, value):
        if isinstance(value, dict):
            value["article_id"] = value.get("article_id") or value.get("id")
            value["description"] = value.get("description") or value.get("summary")
            value["category"] = value.get("category") or value.get("category_name")
            return value
        return _article_to_dict(value)



class ArticleListResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    summary: str | None = None
    source_name: str | None = None
    category_name: str | None = None
    image_url: str | None = None
    published_at: str | None = None
    sentiment: str | None = None
    credibility_score: float | None = None
    tags: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _flatten_orm(cls, value):
        if isinstance(value, dict):
            return value
        data = _article_to_dict(value)
        return {key: data.get(key) for key in cls.model_fields}
