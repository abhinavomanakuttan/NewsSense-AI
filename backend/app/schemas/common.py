from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None


class TimestampSchema(BaseModel):
    created_at: datetime
    updated_at: datetime


class UUIDBaseSchema(BaseModel):
    id: UUID


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
