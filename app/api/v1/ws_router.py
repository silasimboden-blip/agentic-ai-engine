"""WebSocket chat router – v1."""

from fastapi import APIRouter, WebSocket

from app.handlers.ws_connection_handler import ws_connection_handler

ws_router = APIRouter(prefix="/api/v1", tags=["websocket"])


@ws_router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws_connection_handler.handle(ws)
