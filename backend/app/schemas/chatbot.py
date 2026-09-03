from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator


class ChatSource(BaseModel):
    title: str
    url: str
    snippet: str
    relevance_score: float = 0.0


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: list[ChatSource] | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    context: dict | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    conversation_id: str
    confidence: float = 0.0


class ConversationHistory(BaseModel):
    conversation_id: str
    messages: list[ChatMessage]


class ConversationResponse(BaseModel):
    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, value):
        if isinstance(value, dict):
            return value
        return {
            "id": value.id,
            "title": value.title,
            "created_at": value.created_at,
            "updated_at": value.updated_at,
        }


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    sources: list[ChatSource] | None = None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, value):
        if isinstance(value, dict):
            return value
        return {
            "id": value.id,
            "role": value.role,
            "content": value.content,
            "sources": value.sources,
            "created_at": value.created_at,
        }
