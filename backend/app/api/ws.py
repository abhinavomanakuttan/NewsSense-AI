from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.services.ws_manager import connection_manager

router = APIRouter(prefix="/api/v1", tags=["WebSocket"])

HEARTBEAT_INTERVAL = 30.0
PING_TIMEOUT = 60.0


async def _authenticate(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        return str(user_id) if user_id else None
    except Exception:
        return None


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: str | None = None):
    user_id = await _authenticate(token)
    if not user_id:
        await websocket.close(code=4401, reason="Authentication failed")
        return

    await connection_manager.connect(user_id, websocket)
    await websocket.send_json({"type": "connected", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(user_id, websocket)


@router.websocket("/ws/live")
async def live_feed_ws(websocket: WebSocket, token: str | None = None):
    """Real-time breaking news and live story developments WebSocket channel."""
    user_id = await _authenticate(token)
    anon_id = user_id or f"client_{id(websocket)}"

    await connection_manager.connect(anon_id, websocket)
    await websocket.send_json({
        "type": "connected",
        "channel": "live_feed",
        "client_id": anon_id,
        "authenticated": bool(user_id),
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type") or data.get("action")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "subscribe":
                topic = data.get("topic") or "all"
                await websocket.send_json({"type": "subscribed", "topic": topic})
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(anon_id, websocket)


@router.post("/ws/broadcast-event")
async def broadcast_event_update(payload: dict):
    """Trigger a broadcast event update to all active WebSockets (admin/internal trigger)."""
    count = await connection_manager.broadcast({
        "type": "event_update",
        "timestamp": payload.get("timestamp"),
        "event_id": payload.get("event_id"),
        "title": payload.get("title", "Breaking News Update"),
        "message": payload.get("message", "New development added to this story."),
        "importance": payload.get("importance", 0.9),
    })
    return {"status": "broadcasted", "recipients": count}
