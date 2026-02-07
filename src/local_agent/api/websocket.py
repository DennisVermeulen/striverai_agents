import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from local_agent.utils.logging import logger

router = APIRouter()

# Global set of connected WebSocket clients
_clients: set[WebSocket] = set()


async def broadcast(event: dict) -> None:
    """Send an event to all connected WebSocket clients."""
    if not _clients:
        return
    message = json.dumps(event)
    disconnected = set()
    for ws in _clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _clients.difference_update(disconnected)


@router.websocket("/ws")  # mounted at /api/ws via prefix in app.py
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(_clients))
    try:
        while True:
            # Keep connection alive, ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        logger.info("WebSocket client disconnected (%d total)", len(_clients))
