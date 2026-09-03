"""Schemas for News Feed API with multi-faceted filtering."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.article import ArticleListResponse


class NewsFeedResponse(BaseModel):
    """Paginated news feed response."""
    model_config = ConfigDict(from_attributes=True)

    total: int
    skip: int
    limit: int
    articles: list[ArticleListResponse]
    applied_filters: dict[str, Any] = Field(default_factory=dict)
