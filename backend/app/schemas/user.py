from uuid import UUID

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str | None = None
    avatar_url: str | None = None
    role: str
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None


class UserPreferencesResponse(BaseModel):
    preferred_categories: list[str] = []
    preferred_sources: list[str] = []
    preferred_languages: list[str] = ["en"]
    preferred_regions: list[str] = []
    notification_enabled: bool = True
    dark_mode: bool = False
    email_digest_frequency: str = "daily"

    class Config:
        from_attributes = True


class UserPreferencesUpdateRequest(BaseModel):
    preferred_categories: list[str] | None = None
    preferred_sources: list[str] | None = None
    preferred_languages: list[str] | None = None
    preferred_regions: list[str] | None = None
    notification_enabled: bool | None = None
    dark_mode: bool | None = None
    email_digest_frequency: str | None = None
