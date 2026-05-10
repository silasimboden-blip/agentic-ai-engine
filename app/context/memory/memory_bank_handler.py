"""Memory bank handler – wraps ADK VertexAiMemoryBankService for the application."""

from __future__ import annotations

import structlog

from google.adk.memory import VertexAiMemoryBankService

from app import config
from app.context.agent_engine import get_agent_engine_id

logger = structlog.get_logger(__name__)


class MemoryBankHandler:
    """Provides a configured Vertex AI Memory Bank service.

    Initialisation is best-effort: if the Agent Engine cannot be
    created (e.g. region not supported), the handler logs a warning
    and ``service`` returns ``None``.
    """

    def __init__(self) -> None:
        self._service: VertexAiMemoryBankService | None = None
        try:
            agent_engine_id = get_agent_engine_id()
            self._service = VertexAiMemoryBankService(
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.MEMORY_BANK_LOCATION,
                agent_engine_id=agent_engine_id,
            )
            logger.info(
                "Memory bank service initialized",
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.MEMORY_BANK_LOCATION,
                agent_engine_id=agent_engine_id,
            )
        except Exception:
            logger.warning(
                "Memory bank unavailable – running without memory",
                exc_info=True,
            )

    @property
    def service(self) -> VertexAiMemoryBankService | None:
        """The underlying ADK memory bank service, or ``None`` if init failed."""
        return self._service


# ---------------------------------------------------------------------------
# Singleton – shared across all connections for the application lifetime.
# ---------------------------------------------------------------------------

memory_bank_handler = MemoryBankHandler()
