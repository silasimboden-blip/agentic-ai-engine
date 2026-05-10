"""WebSocket connection handler – manages the lifecycle of chat connections."""

import base64
import json

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from app.config import DEFAULT_AGENT_ID
from app.handlers.agent_team_handler import AgentTeamHandler
from app.handlers.session_handler import session_handler

logger = structlog.get_logger(__name__)


class WebSocketConnectionHandler:
    """Manages active WebSocket connections and their message loops.

    A single instance is created at module level and shared by the
    WebSocket router.  Each incoming connection is tracked in
    ``_active_connections`` for potential future broadcasting.
    """

    def __init__(self) -> None:
        self._active_connections: dict[str, WebSocket] = {}

    async def handle(self, ws: WebSocket) -> None:
        """Handle the full lifecycle of a WebSocket chat connection.

        Protocol (JSON messages):
          Client → Server:  {"action": "select_agent", "agent_id": "..."}
          Client → Server:  {"action": "new_session"}
          Client → Server:  {"action": "message", "message": "...", "files": [...]}
          Client → Server:  {"message": "user text"}          (legacy shorthand)
          Server → Client:  {"type": "agent_ready",  "agent_id": "...", "session_id": "..."}
          Server → Client:  {"type": "partial|final", "author": "...", "content": "..."}
          Server → Client:  {"type": "done"}
          Server → Client:  {"type": "error", "author": "system", "content": "..."}
        """
        await ws.accept()
        connection_id = str(id(ws))
        self._active_connections[connection_id] = ws

        # Each connection gets its own handler but shares the app-level
        # session handler so agent sessions persist across reconnections.
        handler = AgentTeamHandler(session_handler)

        try:
            await handler.create_agent_team_runner(DEFAULT_AGENT_ID)
        except Exception as e:
            logger.error("Failed to initialise agent on connect", connection_id=connection_id, error=str(e))
            try:
                await ws.send_json({"type": "error", "author": "system", "content": f"Agent init failed: {e}"})
            except Exception:
                pass
            self._active_connections.pop(connection_id, None)
            await ws.close()
            return

        logger.info("WebSocket connected", connection_id=connection_id, agent_id=DEFAULT_AGENT_ID)

        # Notify client which agent is active
        await ws.send_json({"type": "agent_ready", "agent_id": DEFAULT_AGENT_ID, "session_id": handler.session_id})

        try:
            while True:
                raw = await ws.receive_text()
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, AttributeError):
                    data = {"message": raw.strip()}

                action = data.get("action", "message")

                # ── Agent switching ────────────────────────────────────
                if action == "select_agent":
                    await self._handle_select_agent(ws, handler, data, connection_id)
                    continue

                # ── New session ─────────────────────────────────────
                if action == "new_session":
                    await self._handle_new_session(ws, handler, connection_id)
                    continue

                # ── Chat message ───────────────────────────────────────
                await self._handle_message(ws, handler, data, connection_id)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected", connection_id=connection_id)
        except Exception as e:
            logger.error("WebSocket error", connection_id=connection_id, error=str(e))
            try:
                await ws.send_json({"type": "error", "author": "system", "content": str(e)})
            except Exception:
                pass
        finally:
            self._active_connections.pop(connection_id, None)

    async def _handle_select_agent(
        self,
        ws: WebSocket,
        handler: AgentTeamHandler,
        data: dict,
        connection_id: str,
    ) -> None:
        agent_id = data.get("agent_id", "").strip()
        if not agent_id:
            await ws.send_json({"type": "error", "author": "system", "content": "No agent_id provided."})
            return
        try:
            await handler.switch_agent(agent_id)
            await ws.send_json({"type": "agent_ready", "agent_id": agent_id, "session_id": handler.session_id})
            logger.info("Agent switched", connection_id=connection_id, agent_id=agent_id)
        except ValueError as e:
            await ws.send_json({"type": "error", "author": "system", "content": str(e)})

    async def _handle_new_session(
        self,
        ws: WebSocket,
        handler: AgentTeamHandler,
        connection_id: str,
    ) -> None:
        try:
            session_id = await handler.create_new_session()
            await ws.send_json({"type": "agent_ready", "agent_id": handler.agent_id, "session_id": session_id})
            logger.info("New session created", connection_id=connection_id, session_id=session_id)
        except ValueError as e:
            await ws.send_json({"type": "error", "author": "system", "content": str(e)})

    async def _handle_message(
        self,
        ws: WebSocket,
        handler: AgentTeamHandler,
        data: dict,
        connection_id: str,
    ) -> None:
        user_message = data.get("message", "").strip()
        raw_files = data.get("files", [])

        if not user_message and not raw_files:
            await ws.send_json({"type": "error", "author": "system", "content": "Empty message."})
            return

        # Decode base64 file data into bytes for the handler
        file_parts: list[dict] = []
        for f in raw_files:
            try:
                file_parts.append({
                    "name": f.get("name", "file"),
                    "mime": f.get("mime", "application/octet-stream"),
                    "data": base64.b64decode(f["data"]),
                })
            except Exception:
                logger.warning("Skipping malformed file attachment", name=f.get("name"))

        logger.info(
            "User message received",
            connection_id=connection_id,
            message=user_message,
            file_count=len(file_parts),
        )

        # Stream agent events back over the WebSocket
        async for event_data in handler.stream_agent_response(user_message, files=file_parts):
            await ws.send_json(event_data)

        # Signal that the full response stream is complete
        await ws.send_json({"type": "done"})


# Singleton instance used by the WebSocket router.
ws_connection_handler = WebSocketConnectionHandler()
