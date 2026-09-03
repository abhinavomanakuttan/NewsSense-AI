"""WebSocket endpoint tests using Starlette's TestClient (supports WS)."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app

client = TestClient(app)


def _url(user_id: str) -> str:
    token = create_access_token({"sub": user_id})
    return f"/api/v1/ws/notifications?token={token}"


def test_websocket_connect_returns_connected_and_answers_ping():
    with client.websocket_connect(_url("user-1")) as ws:
        assert ws.receive_json() == {"type": "connected", "user_id": "user-1"}
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_websocket_rejects_invalid_token():
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws/notifications?token=not-a-valid-token") as ws,
    ):
        ws.receive_json()
    assert exc_info.value.code == 4401


def test_websocket_rejects_missing_token():
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws/notifications") as ws,
    ):
        ws.receive_json()
    assert exc_info.value.code == 4401
