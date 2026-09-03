from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.conversation import ChatMessage, Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, db):
        super().__init__(db, Conversation)

    async def get_by_id_and_user(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, user_id: UUID, conversation_id: UUID | None = None
    ) -> Conversation:
        if conversation_id:
            existing = await self.get_by_id_and_user(conversation_id, user_id)
            if existing:
                return existing
        return await self.create(user_id=user_id)

    async def list_user_conversations(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_user_conversations(self, user_id: UUID) -> int:
        stmt = select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def add_message(
        self, conversation_id: UUID, role: str, content: str, sources: list[dict] | None = None
    ) -> ChatMessage:
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def get_messages(self, conversation_id: UUID, limit: int = 200) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .options(selectinload(ChatMessage.conversation))
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
