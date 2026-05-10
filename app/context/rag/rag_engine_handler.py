"""RAG engine handler – manages a Vertex AI RAG corpus for document retrieval.

Auto-provisions a RAG corpus on first use if ``RAG_CORPUS`` is not set.
Provides helpers for importing files and listing documents.
"""

from __future__ import annotations

import asyncio
import threading

import structlog
import vertexai as _vertexai
from vertexai.preview import rag

from app import config

logger = structlog.get_logger(__name__)

_DISPLAY_NAME = "agentic-ai-engineering-rag"


def _get_or_create_corpus() -> str | None:
    """Return the RAG corpus resource name, creating one if needed.

    Temporarily switches the Vertex AI SDK to ``GOOGLE_CLOUD_LOCATION``
    (RAG Engine is regional).

    Returns ``None`` if corpus creation fails.
    """
    if config.RAG_CORPUS:
        logger.info("Using configured RAG corpus", rag_corpus=config.RAG_CORPUS)
        return config.RAG_CORPUS

    # Ensure we're in the right region
    _vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.GOOGLE_CLOUD_LOCATION)
    try:
        # Look for an existing corpus with our display name
        for corpus in rag.list_corpora():
            if corpus.display_name == _DISPLAY_NAME:
                logger.info(
                    "Found existing RAG corpus",
                    corpus_name=corpus.name,
                    display_name=corpus.display_name,
                )
                return corpus.name

        # Create a new corpus
        logger.info("No RAG corpus found, creating a new one", display_name=_DISPLAY_NAME)
        corpus = rag.create_corpus(display_name=_DISPLAY_NAME)
        logger.info("Created RAG corpus", corpus_name=corpus.name)
        return corpus.name
    except Exception:
        logger.warning("RAG corpus unavailable – running without RAG", exc_info=True)
        return None


class RagEngineHandler:
    """Provides a configured RAG corpus for document retrieval.

    Initialisation is lazy and best-effort: the first access to
    ``corpus_name`` or ``available`` triggers corpus provisioning.
    If the corpus cannot be created, ``corpus_name`` stays ``None``
    and the RAG agent is not available.
    """

    def __init__(self) -> None:
        self._corpus_name: str | None = None
        self._initialized = False
        self._lock = threading.Lock()

    def _ensure_initialized(self) -> None:
        """Lazy-init: provision the corpus on first access (thread-safe)."""
        if self._initialized:
            return
        with self._lock:
            if self._initialized:          # double-check after acquiring lock
                return
            try:
                self._corpus_name = _get_or_create_corpus()
            except Exception:
                logger.warning("RAG engine init failed", exc_info=True)
            self._initialized = True

    @property
    def corpus_name(self) -> str | None:
        """Full resource name of the RAG corpus, or ``None``."""
        self._ensure_initialized()
        return self._corpus_name

    @property
    def available(self) -> bool:
        self._ensure_initialized()
        return self._corpus_name is not None

    def _import_files_sync(self, gcs_uris: list[str]) -> dict:
        """Synchronous implementation of file import."""
        _vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.GOOGLE_CLOUD_LOCATION)
        response = rag.import_files(
            corpus_name=self._corpus_name,
            paths=gcs_uris,
            chunk_size=1024,
            chunk_overlap=200,
        )
        logger.info(
            "Files imported into RAG corpus",
            corpus=self._corpus_name,
            imported=response.imported_rag_files_count,
        )
        return {
            "status": "ok",
            "imported_count": response.imported_rag_files_count,
        }

    async def import_files(self, gcs_uris: list[str]) -> dict:
        """Import files from GCS URIs into the corpus.

        Args:
            gcs_uris: List of ``gs://bucket/path`` URIs.

        Returns:
            A summary dict with status and imported count.
        """
        if not self.available:
            return {"status": "error", "message": "RAG corpus not available"}
        try:
            return await asyncio.to_thread(self._import_files_sync, gcs_uris)
        except Exception as e:
            logger.error("Failed to import files", error=str(e))
            return {"status": "error", "message": str(e)}

    def _list_files_sync(self) -> list[dict]:
        """Synchronous implementation of file listing."""
        _vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.GOOGLE_CLOUD_LOCATION)
        files = list(rag.list_files(corpus_name=self._corpus_name))
        return [
            {
                "name": f.name,
                "display_name": f.display_name,
                "size_bytes": f.size_bytes,
            }
            for f in files
        ]

    async def list_files(self) -> list[dict]:
        """List files currently in the corpus."""
        if not self.available:
            return []
        try:
            return await asyncio.to_thread(self._list_files_sync)
        except Exception as e:
            logger.error("Failed to list RAG files", error=str(e))
            return []

    def _delete_file_sync(self, file_name: str) -> dict:
        """Synchronous implementation of file deletion."""
        _vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.GOOGLE_CLOUD_LOCATION)
        rag.delete_file(name=file_name)
        logger.info("Deleted RAG file", file_name=file_name)
        return {"status": "ok"}

    async def delete_file(self, file_name: str) -> dict:
        """Delete a file from the corpus by resource name."""
        if not self.available:
            return {"status": "error", "message": "RAG corpus not available"}
        try:
            return await asyncio.to_thread(self._delete_file_sync, file_name)
        except Exception as e:
            logger.error("Failed to delete RAG file", error=str(e))
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

rag_engine_handler = RagEngineHandler()
