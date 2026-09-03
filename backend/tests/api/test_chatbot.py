import pytest

from tests.services.test_chatbot_service import FakeQAModule, FakeVectorStore


@pytest.fixture
def chat_fakes(monkeypatch):
    monkeypatch.setattr("app.services.chatbot_service.QAModule", FakeQAModule)
    monkeypatch.setattr(
        "app.services.chatbot_service.get_vector_store",
        lambda: FakeVectorStore(available=False),
    )


async def test_post_chat_returns_answer_and_sources(
    client, auth_headers, article_fixture, chat_fakes
):
    resp = await client.post(
        "/api/v1/chat",
        json={"message": "AI breakthrough"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["answer"] == "Test answer"
    assert data["conversation_id"]
    assert data["sources"]
    assert data["sources"][0]["title"] == article_fixture["title"]


async def test_post_chat_requires_auth(client, chat_fakes):
    resp = await client.post("/api/v1/chat", json={"message": "hello"})
    assert resp.status_code == 401


async def test_conversation_lifecycle(client, auth_headers, article_fixture, chat_fakes):
    created = await client.post(
        "/api/v1/chat",
        json={"message": "first question"},
        headers=auth_headers,
    )
    conversation_id = created.json()["conversation_id"]

    listed = await client.get("/api/v1/chat/conversations", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["conversations"][0]["id"] == conversation_id
    assert body["conversations"][0]["title"] == "first question"

    history = await client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=auth_headers
    )
    assert history.status_code == 200
    messages = history.json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "first question"

    deleted = await client.delete(
        f"/api/v1/chat/conversations/{conversation_id}", headers=auth_headers
    )
    assert deleted.status_code == 204

    gone = await client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=auth_headers)
    assert gone.status_code == 404


async def test_get_unknown_conversation_returns_404(client, auth_headers, chat_fakes):
    resp = await client.get(
        "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_delete_unknown_conversation_returns_404(client, auth_headers, chat_fakes):
    resp = await client.delete(
        "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404
