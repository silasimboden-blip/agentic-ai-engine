"""Application configuration and structured logging setup."""

import logging
import os

import structlog

import vertexai

# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------
# Cloud Run sets K_SERVICE automatically; if present we are running in the cloud.
IS_CLOUD_RUN: bool = "K_SERVICE" in os.environ

# Only load .env file for local development
if not IS_CLOUD_RUN:
    from dotenv import load_dotenv
    load_dotenv()


# ---------------------------------------------------------------------------
# Application settings
# ---------------------------------------------------------------------------

USER_ID = "user-12345"  # In a real application, this would be dynamic and based on the authenticated user

# Automatically set to "gcp" on Cloud Run, "console" locally
LOG_ENV: str = "gcp" if IS_CLOUD_RUN else "console"

# Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# ---------------------------------------------------------------------------
# Google Cloud Platform settings (from env vars)
# ---------------------------------------------------------------------------

GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "agentic-ai-eng-489113")
GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-north1")
GOOGLE_CLOUD_STORAGE_BUCKET: str = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET", "agentic-ai-eng-bucket")

# Default agent to use when a connection starts
DEFAULT_AGENT_ID: str = os.getenv("DEFAULT_AGENT_ID", "greeting_agent")

# Default LLM model for agents
DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "gemini-2.5-flash")

# Vertex AI Agent Engine ID (required for Memory Bank)
AGENT_ENGINE_ID: str = os.getenv("AGENT_ENGINE_ID", "")

# Location for Memory Bank / ReasoningEngine (not available in all regions)
MEMORY_BANK_LOCATION: str = os.getenv("MEMORY_BANK_LOCATION", "us-central1")

# MCP Fetch server URL (Streamable HTTP endpoint, e.g. http://localhost:8765/mcp).
# When empty, the summarizer agent runs without the fetch_url tool.
MCP_FETCH_URL: str = os.getenv("MCP_FETCH_URL", "")

# Session backend: "VERTEX" for VertexAiSessionService, "IN_MEMORY" for InMemorySessionService.
# Defaults to "IN_MEMORY" locally, "VERTEX" on Cloud Run.
SESSION_BACKEND: str = os.getenv("SESSION_BACKEND", "VERTEX" if IS_CLOUD_RUN else "IN_MEMORY")

# Vertex AI RAG Engine corpus resource name (auto-created if empty).
# Format: projects/{project}/locations/{location}/ragCorpora/{id}
RAG_CORPUS: str = os.getenv("RAG_CORPUS", "")

# ---------------------------------------------------------------------------
# A2A (Agent-to-Agent) settings — external critic agent
# ---------------------------------------------------------------------------

# URL of the critic agent's A2A Agent Card (used by the summarizer to connect).
CRITIC_A2A_URL: str = os.getenv("CRITIC_A2A_URL", "http://localhost:8001/.well-known/agent.json")

# Host and port for the critic A2A server itself.
CRITIC_A2A_HOST: str = os.getenv("CRITIC_A2A_HOST", "localhost")
CRITIC_A2A_PORT: int = int(os.getenv("CRITIC_A2A_PORT", "8001"))


# ---------------------------------------------------------------------------
# Google Vertex AI initialization
# ---------------------------------------------------------------------------

# Skip vertexai.init() when running outside GCP (e.g. Hugging Face Spaces)
# and using the Google AI API key backend instead.
if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE").upper() == "TRUE":
    vertexai.init(
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION,
    )

# ---------------------------------------------------------------------------
# Structlog configuration
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Configure structlog for either local console or GCP Cloud Logging.

    Call this once at application startup (e.g. in main.py / entrypoint).

    LOG_ENV="console"  → coloured, human-readable dev output
    LOG_ENV="gcp"      → JSON lines compatible with GCP Cloud Logging
    """
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # Shared processors applied to every log event
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if LOG_ENV == "gcp":
        # GCP Cloud Logging expects JSON with specific field names.
        # "severity" is mapped from the log level by the GCP processor.
        shared_processors += [
            # Rename "level" → "severity" for Cloud Logging
            _rename_level_to_severity,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Local / console development output
        shared_processors += [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libraries respect the level
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )


def _rename_level_to_severity(
    logger: logging.Logger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Rename ``level`` to ``severity`` for GCP Cloud Logging compatibility."""
    level = event_dict.pop("level", method_name)
    event_dict["severity"] = level.upper()
    return event_dict