from uuid import UUID

import pytest

from app.repositories.article_repository import ArticleRepository
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chatbot import ChatRequest
from app.services.chatbot_service import ChatbotService


class FakeEmbedder:
    model = object()

    async def process(self, data: dict) -> dict:
        return {"embedding": [0.1, 0.2, 0.3], "dimension": 3}


class FakeVectorStore:
    def __init__(self, hits=None, available: bool = True):
        self._hits = hits or []
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def search(self, embedding, limit=10, score_threshold=None):
        return self._hits


class FakeQAModule:
    def __init__(self, answer: str = "Test answer", raise_on_process: bool = False):
        self._answer = answer
        self._raise_on_process = raise_on_process

    async def process(self, data: dict) -> dict:
        if self._raise_on_process:
            raise RuntimeError("qa failed")
        return {
            "answer": self._answer,
            "confidence": 0.9,
            "question": data["question"],
            "context_length": len(data["context"]),
        }


@pytest.fixture
async def chat_article(db_session, source_fixture, category_fixture) -> dict:
    repo = ArticleRepository(db_session)
    article = await repo.create(
        title="AI Breakthrough in Health",
        slug="ai-breakthrough-health",
        url="https://testnews.com/ai-health",
        content="Scientists announced a breakthrough in AI-assisted diagnostics using deep learning.",
        summary="AI helps doctors diagnose faster.",
        content_hash="test-hash-chat-1",
        source_id=source_fixture["id"],
        category_id=category_fixture["id"],
        published_at="2026-07-30T10:00:00",
    )
    await db_session.flush()
    return {"id": article.id, "title": article.title, "url": article.url}


def _make_service(db_session, article_repo, vector_store=None, qa_module=None):
    return ChatbotService(
        conversation_repo=ConversationRepository(db_session),
        article_repo=article_repo,
        embedder=FakeEmbedder(),
        vector_store=vector_store or FakeVectorStore(),
        qa_module=qa_module or FakeQAModule(),
    )


@pytest.mark.asyncio
async def test_chat_uses_vector_retrieval_and_persists_messages(
    db_session, chat_article, regular_user
):
    article_repo = ArticleRepository(db_session)
    vector_store = FakeVectorStore(
        hits=[{"id": f"article_{chat_article['id']}", "score": 0.85, "payload": {}}]
    )
    service = _make_service(db_session, article_repo, vector_store=vector_store)

    response = await service.chat(
        regular_user["id"], ChatRequest(message="What is the AI breakthrough?")
    )

    assert response.answer == "Test answer"
    assert response.confidence == 0.9
    assert response.sources[0].title == chat_article["title"]
    assert response.sources[0].relevance_score == 0.85
    assert response.conversation_id

    messages = await service.get_history(regular_user["id"], UUID(response.conversation_id))
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "What is the AI breakthrough?"
    assert messages[1].content == "Test answer"
    assert messages[1].sources[0].title == chat_article["title"]


@pytest.mark.asyncio
async def test_chat_falls_back_to_keyword_search_when_vector_store_unavailable(
    db_session, chat_article, regular_user
):
    article_repo = ArticleRepository(db_session)
    service = _make_service(db_session, article_repo, vector_store=FakeVectorStore(available=False))

    response = await service.chat(regular_user["id"], ChatRequest(message="deep learning"))

    assert response.answer == "Test answer"
    assert any(s.title == chat_article["title"] for s in response.sources)


@pytest.mark.asyncio
async def test_chat_uses_fallback_answer_when_qa_fails(db_session, chat_article, regular_user):
    article_repo = ArticleRepository(db_session)
    vector_store = FakeVectorStore(
        hits=[{"id": f"article_{chat_article['id']}", "score": 0.85, "payload": {}}]
    )
    service = _make_service(
        db_session,
        article_repo,
        vector_store=vector_store,
        qa_module=FakeQAModule(raise_on_process=True),
    )

    response = await service.chat(
        regular_user["id"], ChatRequest(message="What is the AI breakthrough?")
    )

    assert "couldn't generate" in response.answer
    assert response.confidence == 0.0
    assert response.sources


@pytest.mark.asyncio
async def test_chat_uses_fallback_message_when_answer_is_empty(
    db_session, chat_article, regular_user
):
    article_repo = ArticleRepository(db_session)
    service = _make_service(db_session, article_repo, qa_module=FakeQAModule(answer=""))

    response = await service.chat(
        regular_user["id"], ChatRequest(message="What is the AI breakthrough?")
    )

    assert "couldn't find a clear answer" in response.answer


@pytest.mark.asyncio
async def test_chat_reuses_existing_conversation(db_session, chat_article, regular_user):
    article_repo = ArticleRepository(db_session)
    service = _make_service(db_session, article_repo)

    first = await service.chat(regular_user["id"], ChatRequest(message="First question"))
    second = await service.chat(
        regular_user["id"],
        ChatRequest(message="Second question", conversation_id=first.conversation_id),
    )

    assert second.conversation_id == first.conversation_id
    messages = await service.get_history(regular_user["id"], UUID(first.conversation_id))
    assert len(messages) == 4
    assert messages[2].content == "Second question"


@pytest.mark.asyncio
async def test_chat_sets_title_from_first_message(db_session, chat_article, regular_user):
    article_repo = ArticleRepository(db_session)
    service = _make_service(db_session, article_repo)

    await service.chat(regular_user["id"], ChatRequest(message="This is the opening question"))

    conversations = await service.list_conversations(regular_user["id"])
    assert conversations.total == 1
    assert conversations.conversations[0].title == "This is the opening question"


@pytest.mark.asyncio
async def test_list_conversations_only_returns_own(db_session, chat_article, regular_user):
    article_repo = ArticleRepository(db_session)
    service = _make_service(db_session, article_repo)

    await service.chat(regular_user["id"], ChatRequest(message="Question one"))
    await service.chat(regular_user["id"], ChatRequest(message="Question two"))

    conversations = await service.list_conversations(regular_user["id"])
    assert conversations.total == 2


@pytest.mark.asyncio
async def test_delete_conversation(db_session, chat_article, regular_user):
    article_repo = ArticleRepository(db_session)
    service = _make_service(db_session, article_repo)

    response = await service.chat(regular_user["id"], ChatRequest(message="Delete me"))

    assert await service.delete_conversation(regular_user["id"], UUID(response.conversation_id))
    assert not await service.delete_conversation(regular_user["id"], UUID(response.conversation_id))
    assert (await service.list_conversations(regular_user["id"])).total == 0
