from uuid import UUID

from pydantic import BaseModel, model_validator


class SourceResponse(BaseModel):
    id: UUID
    source_id: UUID | None = None
    name: str
    url: str
    domain: str | None = None
    feed_url: str | None = None
    rss_url: str | None = None
    api_endpoint: str | None = None
    source_type: str
    language: str = "en"
    country: str | None = None
    category: str | None = None
    is_active: bool = True
    active: bool = True
    reliability_score: float = 0.5
    reputation_score: float = 0.5
    fetch_interval_minutes: int = 15
    rate_limit: int = 60
    priority: str = "normal"
    last_fetched_at: str | None = None
    last_fetched: str | None = None
    consecutive_failures: int = 0
    config: str | None = None

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _populate_aliases(cls, value):
        if hasattr(value, "id") and not isinstance(value, dict):
            # SQLAlchemy ORM objects have __table__; SimpleNamespace objects do not
            if hasattr(value, "__table__"):
                d = {c.name: getattr(value, c.name, None) for c in value.__table__.columns}
            else:
                # Fallback for SimpleNamespace and other objects (used in tests)
                d = {k: v for k, v in vars(value).items()} if hasattr(value, "__dict__") else {}
                if not d:
                    d = {"id": value.id}
            d["source_id"] = getattr(value, "id", None)
            d["rss_url"] = getattr(value, "feed_url", None)
            d["active"] = getattr(value, "is_active", getattr(value, "active", True))
            d["last_fetched"] = getattr(value, "last_fetched_at", getattr(value, "last_fetched", None))
            d["reputation_score"] = getattr(value, "reliability_score", getattr(value, "reputation_score", 0.5))
            # Populate required fields that might be missing
            for field in ("name", "url", "source_type"):
                if field not in d:
                    d[field] = getattr(value, field, "")
            return d
        if isinstance(value, dict):
            value["source_id"] = value.get("source_id") or value.get("id")
            value["rss_url"] = value.get("rss_url") or value.get("feed_url")
            value["active"] = value.get("active", value.get("is_active", True))
            value["last_fetched"] = value.get("last_fetched") or value.get("last_fetched_at")
            value["reputation_score"] = value.get("reputation_score", value.get("reliability_score", 0.5))
            return value
        return value



class SourceCreateRequest(BaseModel):
    name: str
    url: str
    domain: str | None = None
    feed_url: str | None = None
    rss_url: str | None = None
    api_endpoint: str | None = None
    source_type: str = "rss"
    language: str = "en"
    country: str | None = None
    category: str | None = None
    reliability_score: float = 0.5
    fetch_interval_minutes: int = 15
    rate_limit: int = 60
    priority: str = "normal"
    active: bool = True
    config: str | None = None


class SourceUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    domain: str | None = None
    feed_url: str | None = None
    rss_url: str | None = None
    api_endpoint: str | None = None
    source_type: str | None = None
    language: str | None = None
    country: str | None = None
    category: str | None = None
    is_active: bool | None = None
    active: bool | None = None
    reliability_score: float | None = None
    fetch_interval_minutes: int | None = None
    rate_limit: int | None = None
    priority: str | None = None
    config: str | None = None

