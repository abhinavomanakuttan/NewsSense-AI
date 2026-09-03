"""RAG chatbot service.

Pipeline: persist the user message, retrieve relevant articles (vector-first
with a SQL keyword fallback), chunk the context with LangChain, generate an
answer with the QA module, and persist the assistant message with sources.
All heavy components (embedder, vector store, QA module) are injectable so
tests can substitute fakes without loading models.
"""

from __future__ import annotations

import logging
from uuid import UUID

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ai.embeddings import EmbeddingGenerator
from app.ai.qa_chain import QAModule
from app.repositories.article_repository import ArticleRepository
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chatbot import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSource,
    ConversationListResponse,
    ConversationResponse,
)
from app.services.vector_store_service import VectorStoreService, get_vector_store

logger = logging.getLogger(__name__)

TOP_K = 5
MAX_CONTEXT_CHARS = 4000
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 100


def _point_id_to_article_id(point_id: str) -> str | None:
    if point_id.startswith("article_"):
        return point_id[len("article_") :]
    return point_id


def _snippet_of(article) -> str:
    text = article.summary or article.content or ""
    return text[:300]


class ChatbotService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        article_repo: ArticleRepository,
        embedder: EmbeddingGenerator | None = None,
        vector_store: VectorStoreService | None = None,
        qa_module: QAModule | None = None,
    ):
        self.conversation_repo = conversation_repo
        self.article_repo = article_repo
        self.embedder = embedder or EmbeddingGenerator()
        self.vector_store = vector_store or get_vector_store()
        self.qa_module = qa_module or QAModule()

    async def chat(self, user_id: UUID, request: ChatRequest) -> ChatResponse:
        conversation = await self.conversation_repo.get_or_create(
            user_id, UUID(request.conversation_id) if request.conversation_id else None
        )
        await self.conversation_repo.add_message(
            conversation.id, role="user", content=request.message
        )

        articles = await self._retrieve(request.message)
        sources = [
            ChatSource(
                title=a.title,
                url=a.url,
                snippet=_snippet_of(a),
                relevance_score=round(score, 4),
            )
            for a, score in articles
        ]

        context = self._build_context([a for a, _ in articles])
        try:
            answer_result = await self.qa_module.process(
                {"question": request.message, "context": context}
            )
            answer = answer_result.get("answer") or ""
            confidence = float(answer_result.get("confidence") or 0.0)
        except Exception as exc:
            logger.error(f"QA generation failed: {exc}")
            answer = (
                "I found relevant articles but couldn't generate an answer right now. "
                "Check the sources below for details."
            )
            confidence = 0.0

        if not answer.strip():
            answer = (
                "I couldn't find a clear answer in the retrieved articles. "
                "Check the sources below for details."
            )

        await self.conversation_repo.add_message(
            conversation.id,
            role="assistant",
            content=answer,
            sources=[s.model_dump() for s in sources],
        )

        if conversation.title is None and len(request.message) > 0:
            conversation.title = request.message[:80]
            await self.conversation_repo.db.flush()

        return ChatResponse(
            answer=answer,
            sources=sources,
            conversation_id=str(conversation.id),
            confidence=confidence,
        )

    async def _retrieve(self, question: str) -> list[tuple[object, float]]:
        """Return (article, relevance_score) pairs, vector-first with SQL fallback."""
        ids_with_scores = await self._vector_retrieve(question)
        if ids_with_scores:
            articles_by_id = await self._fetch_articles(
                {article_id for article_id, _ in ids_with_scores}
            )
            if articles_by_id:
                return [
                    (articles_by_id[article_id], score)
                    for article_id, score in ids_with_scores
                    if article_id in articles_by_id
                ]

        return await self._keyword_retrieve(question)

    async def _vector_retrieve(self, question: str) -> list[tuple[str, float]]:
        if not self.vector_store.is_available():
            return []
        try:
            if self.embedder.model is None:
                await self.embedder.initialize()
            embedding = await self.embedder.process({"text": question})
            hits = self.vector_store.search(embedding.get("embedding", []), limit=TOP_K)
            return [
                (_point_id_to_article_id(hit["id"]), float(hit.get("score", 0.0)))
                for hit in hits
                if _point_id_to_article_id(hit["id"])
            ]
        except Exception as exc:
            logger.warning(f"Vector retrieval failed; falling back to keyword search: {exc}")
            return []

    async def _keyword_retrieve(self, question: str) -> list[tuple[object, float]]:
        articles, _ = await self.article_repo.search_by_keywords(question, limit=TOP_K)
        return [(a, 1.0) for a in articles]

    async def _fetch_articles(self, article_ids: set[str]) -> dict[str, object]:
        articles = {}
        for article_id in article_ids:
            try:
                article = await self.article_repo.get_by_id(UUID(article_id))
            except (ValueError, TypeError):
                continue
            if article:
                articles[article_id] = article
        return articles

    def _build_context(self, articles: list[object]) -> str:
        documents = [
            Document(
                page_content=f"{a.title}\n{(a.summary or '')} {(a.content or '')}",
                metadata={"id": str(a.id), "title": a.title},
            )
            for a in articles
        ]
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=_CHUNK_SIZE,
            chunk_overlap=_CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(documents)

        context = ""
        for chunk in chunks:
            piece = f"[{chunk.metadata.get('title', 'article')}]\n{chunk.page_content}\n\n"
            if len(context) + len(piece) > MAX_CONTEXT_CHARS:
                break
            context += piece
        return context

    async def list_conversations(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> ConversationListResponse:
        conversations = await self.conversation_repo.list_user_conversations(user_id, skip, limit)
        total = await self.conversation_repo.count_user_conversations(user_id)
        return ConversationListResponse(
            conversations=[ConversationResponse.model_validate(c) for c in conversations],
            total=total,
        )

    async def get_history(self, user_id: UUID, conversation_id: UUID) -> list[ChatMessageResponse]:
        conversation = await self.conversation_repo.get_by_id_and_user(conversation_id, user_id)
        if not conversation:
            return []
        messages = await self.conversation_repo.get_messages(conversation_id)
        return [ChatMessageResponse.model_validate(m) for m in messages]

    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> bool:
        conversation = await self.conversation_repo.get_by_id_and_user(conversation_id, user_id)
        if not conversation:
            return False
        await self.conversation_repo.delete(conversation_id)
        return True
