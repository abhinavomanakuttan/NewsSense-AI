import pytest

from app.services.ws_manager import ConnectionManager


class FakeWebSocket:
    def __init__(self):
        self.sent: list[dict] = []
        self.closed = False

    async def accept(self):
        pass

    async def send_text(self, payload: str) -> None:
        import json

        self.sent.append(json.loads(payload))

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_connect_disconnect_manages_registry():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("user-1", ws)

    assert manager.is_connected("user-1")
    assert manager.user_count() == 1

    await manager.disconnect("user-1", ws)
    assert not manager.is_connected("user-1")
    assert manager.user_count() == 0


@pytest.mark.asyncio
async def test_multiple_sockets_per_user_receive_push():
    manager = ConnectionManager()
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()
    await manager.connect("user-1", ws1)
    await manager.connect("user-1", ws2)

    delivered = await manager.send_to_user("user-1", {"type": "notification", "hi": 1})

    assert delivered is True
    assert ws1.sent == [{"type": "notification", "hi": 1}]
    assert ws2.sent == [{"type": "notification", "hi": 1}]


@pytest.mark.asyncio
async def test_send_to_user_without_connection_returns_false():
    manager = ConnectionManager()
    assert await manager.send_to_user("ghost", {"type": "notification"}) is False


@pytest.mark.asyncio
async def test_broken_socket_is_removed_on_send():
    manager = ConnectionManager()

    class BrokenSocket(FakeWebSocket):
        async def send_text(self, payload: str) -> None:
            raise RuntimeError("socket died")

    ws = BrokenSocket()
    await manager.connect("user-1", ws)

    delivered = await manager.send_to_user("user-1", {"type": "notification"})

    assert delivered is False
    assert not manager.is_connected("user-1")
