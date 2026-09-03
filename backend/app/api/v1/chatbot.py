from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import (
    get_article_repo,
    get_conversation_repo,
    get_current_user,
)
from app.repositories.article_repository import ArticleRepository
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chatbot import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
)
from app.services.chatbot_service import ChatbotService

router = APIRouter(prefix="/chat", tags=["Chatbot"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user=Depends(get_current_user),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = ChatbotService(conversation_repo=conversation_repo, article_repo=article_repo)
    return await service.chat(user.id, request)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
):
    service = ChatbotService(conversation_repo=conversation_repo, article_repo=None)
    return await service.list_conversations(user.id, skip, limit)


@router.get("/conversations/{conversation_id}", response_model=list[ChatMessageResponse])
async def get_conversation(
    conversation_id: UUID,
    user=Depends(get_current_user),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
):
    service = ChatbotService(conversation_repo=conversation_repo, article_repo=None)
    messages = await service.get_history(user.id, conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return messages


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    user=Depends(get_current_user),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
):
    service = ChatbotService(conversation_repo=conversation_repo, article_repo=None)
    deleted = await service.delete_conversation(user.id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
