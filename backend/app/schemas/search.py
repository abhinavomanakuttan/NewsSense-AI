from pydantic import BaseModel


class SearchResultItem(BaseModel):
    id: str
    title: str
    slug: str
    summary: str | None = None
    url: str
    source_name: str | None = None
    category_name: str | None = None
    published_at: str | None = None
    score: float = 0.0
    highlights: dict | None = None


class SearchRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 20
    category: str | None = None
    source: str | None = None
    language: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    sentiment: str | None = None
    sort_by: str = "relevance"
    sort_order: str = "desc"


class SearchResponse(BaseModel):
    query: str
    total: int
    page: int
    page_size: int
    results: list[SearchResultItem]
    facets: dict | None = None
