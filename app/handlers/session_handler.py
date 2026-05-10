"""Session handler – manages one persistent session per agent.

Sessions are keyed by ``agent_id``.  On Cloud Run the handler uses
``VertexAiSessionService`` so sessions survive restarts and scale-out.
Locally it falls back to ``InMemorySessionService`` when the Vertex AI
backend is unavailable.
"""

import structlog

from google.adk.sessions import InMemorySessionService, Session, VertexAiSessionService

from app import config
from app.context.agent_engine import get_agent_engine_id

logger = structlog.get_logger(__name__)


def _create_session_service() -> InMemorySessionService | VertexAiSessionService:
    """Create the session service based on ``SESSION_BACKEND`` config.

    - ``"vertex"`` → VertexAiSessionService (persistent, requires Agent Engine)
    - ``"inmemory"`` → InMemorySessionService (fast, sessions lost on restart)
    """
    if config.SESSION_BACKEND != "VERTEX":
        logger.info("Using InMemorySessionService (SESSION_BACKEND=%s)", config.SESSION_BACKEND)
        return InMemorySessionService()

    try:
        agent_engine_id = get_agent_engine_id()
        svc = VertexAiSessionService(
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.MEMORY_BANK_LOCATION,
            agent_engine_id=agent_engine_id,
        )
        logger.info(
            "Using VertexAiSessionService",
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.MEMORY_BANK_LOCATION,
            agent_engine_id=agent_engine_id,
        )
        return svc
    except Exception:
        logger.warning(
            "VertexAiSessionService unavailable – falling back to InMemorySessionService",
            exc_info=True,
        )
        return InMemorySessionService()


class SessionHandler:
    """Owns the ADK session service and keeps one session alive per agent.

    A single instance of this class should be created at application startup
    and shared across all connections / handlers.
    """

    def __init__(self) -> None:
        self._service = _create_session_service()
        self._agent_session_mapping: dict[str, str] = {}  # agent_id -> session_id

    @property
    def service(self) -> InMemorySessionService | VertexAiSessionService:
        """The underlying ADK session service (required by ``Runner``)."""
        return self._service

    async def get_or_create_session(self, app_name: str, agent_id: str) -> Session:
        """Return the existing session for *agent_id*, or create a new one.

        If a session for *agent_id* already exists in memory it is returned
        unchanged, preserving the full conversation history.  A new session is
        only created the first time a particular agent is used.
        """
        if agent_id in self._agent_session_mapping:
            session = await self._service.get_session(
                app_name=app_name,
                user_id=config.USER_ID,
                session_id=self._agent_session_mapping[agent_id],
            )
            if session is not None:
                logger.debug(
                    "Reusing existing session",
                    agent_id=agent_id,
                    session_id=session.id,
                )
                return session

        session = await self._service.create_session(
            app_name=app_name,
            user_id=config.USER_ID,
        )

        self._agent_session_mapping[agent_id] = session.id

        logger.info(
            "Created new session for agent",
            agent_id=agent_id,
            session_id=session.id,
        )
        return session

    async def reset_session(self, app_name: str, agent_id: str) -> Session:
        """Discard the current session for *agent_id* and create a fresh one."""
        self._agent_session_mapping.pop(agent_id, None)
        return await self.get_or_create_session(app_name, agent_id)


# ---------------------------------------------------------------------------
# Singleton – single instance shared across all connections for the entire
# application lifetime, so agent sessions persist across WebSocket reconnections.
# ---------------------------------------------------------------------------

session_handler = SessionHandler()
