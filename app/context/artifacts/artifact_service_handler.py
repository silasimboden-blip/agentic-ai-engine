"""Artifact service handler – wraps ADK GcsArtifactService for the application."""

import structlog

from google.adk.artifacts import GcsArtifactService

from app import config

logger = structlog.get_logger(__name__)


class ArtifactServiceHandler:
    """Provides a configured GCS-backed artifact service.

    A single instance should be created at application startup and
    shared across all handlers / connections.
    """

    def __init__(self) -> None:
        self._service = GcsArtifactService(
            bucket_name=config.GOOGLE_CLOUD_STORAGE_BUCKET,
        )
        logger.info(
            "Artifact service initialized",
            bucket=config.GOOGLE_CLOUD_STORAGE_BUCKET,
        )

    @property
    def service(self) -> GcsArtifactService:
        """The underlying ADK artifact service (required by ``Runner``)."""
        return self._service


# ---------------------------------------------------------------------------
# Singleton – shared across all connections for the application lifetime.
# ---------------------------------------------------------------------------

artifact_service_handler = ArtifactServiceHandler()
