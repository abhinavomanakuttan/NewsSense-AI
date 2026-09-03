"""Per-user WebSocket connection registry for real-time pushes.

A process-local registry keyed by user id. Each connected socket belongs to
the user who authenticated; notifications are routed to every socket the user
has open (multiple tabs/workers). Cross-process fan-out is handled by the
notification dispatcher via Redis pub/sub.
"""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from typing import Any

from fastapi import WebSocket

from app.core.metrics import WS_CONNECTIONS_ACTIVE

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(user_id, set()).add(websocket)
        WS_CONNECTIONS_ACTIVE.inc()
        logger.info(f"WebSocket connected for user {user_id}")

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(user_id, None)
        WS_CONNECTIONS_ACTIVE.dec()
        logger.info(f"WebSocket disconnected for user {user_id}")

    def is_connected(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def user_count(self) -> int:
        return len(self._connections)

    async def send_to_user(self, user_id: str, payload: dict[str, Any]) -> bool:
        sockets = self._connections.get(user_id)
        if not sockets:
            return False
        sent_any = False
        for websocket in list(sockets):
            try:
                await websocket.send_text(json.dumps(payload))
                sent_any = True
            except Exception as exc:
                logger.warning(f"Failed to send to user {user_id}: {exc}")
                await self.disconnect(user_id, websocket)
        return sent_any

    async def broadcast(self, payload: dict[str, Any]) -> int:
        """Broadcast payload to all active WebSocket connections across all users."""
        count = 0
        for user_id, sockets in list(self._connections.items()):
            for websocket in list(sockets):
                try:
                    await websocket.send_text(json.dumps(payload))
                    count += 1
                except Exception as exc:
                    logger.warning(f"Broadcast failed for connection: {exc}")
                    await self.disconnect(user_id, websocket)
        return count

    async def close_all(self) -> None:
        for sockets in list(self._connections.values()):
            for websocket in list(sockets):
                with suppress(Exception):
                    await websocket.close()
        self._connections.clear()


connection_manager = ConnectionManager()

# Alias for backwards compatibility
WebSocketManager = ConnectionManager
