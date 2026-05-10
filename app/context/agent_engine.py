"""Shared Agent Engine provider – resolves or creates the Agent Engine ID.

Both the session handler and the memory bank handler require an
``agent_engine_id`` backed by Vertex AI Agent Engine.  This module
centralises that resolution so it only happens once per process.
"""

from __future__ import annotations

import structlog
import vertexai as _vertexai

from vertexai import agent_engines

from app import config

logger = structlog.get_logger(__name__)

_DISPLAY_NAME = "agentic-ai-engineering-memory"

# Cached value – populated on first call to ``get_agent_engine_id()``.
_cached_id: str | None = None


def get_agent_engine_id() -> str:
    """Return the Agent Engine ID, creating a bare engine if needed.

    Uses ``MEMORY_BANK_LOCATION`` because ReasoningEngine is not available
    in every region.  Temporarily re-initialises the Vertex AI SDK with
    the memory-bank region, then restores the original location.

    The result is cached for the lifetime of the process.
    """
    global _cached_id
    if _cached_id is not None:
        return _cached_id

    if config.AGENT_ENGINE_ID:
        logger.info("Using configured Agent Engine ID", agent_engine_id=config.AGENT_ENGINE_ID)
        _cached_id = config.AGENT_ENGINE_ID
        return _cached_id

    # Temporarily switch to the memory-bank region
    _vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.MEMORY_BANK_LOCATION)
    try:
        # Search for an existing engine with our display name
        for engine in agent_engines.list(filter=f'display_name="{_DISPLAY_NAME}"'):
            engine_id = engine.resource_name.rsplit("/", 1)[-1]
            logger.info(
                "Found existing Agent Engine",
                agent_engine_id=engine_id,
                resource_name=engine.resource_name,
            )
            _cached_id = engine_id
            return _cached_id

        # None found – create a bare engine (no deployed code, just the resource)
        logger.info("No Agent Engine found, creating a new one", display_name=_DISPLAY_NAME)
        engine = agent_engines.create(display_name=_DISPLAY_NAME)
        engine_id = engine.resource_name.rsplit("/", 1)[-1]
        logger.info(
            "Created Agent Engine",
            agent_engine_id=engine_id,
            resource_name=engine.resource_name,
        )
        _cached_id = engine_id
        return _cached_id
    finally:
        # Restore original location for all other Vertex AI calls
        _vertexai.init(project=config.GOOGLE_CLOUD_PROJECT, location=config.GOOGLE_CLOUD_LOCATION)
