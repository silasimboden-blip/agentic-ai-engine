"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.v1.agent_router import agent_router
from app.api.v1.ws_router import ws_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan – startup / shutdown hooks."""
    logger.info("FastAPI application starting")
    yield
    logger.info("FastAPI application shutting down")


def create_app() -> FastAPI:
    """Factory that builds and returns the FastAPI application."""

    app = FastAPI(
        title="Agentic AI Engineering",
        description="Chat with AI agent teams via WebSocket.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Mount static assets (CSS, JS, images) ─────────────────────────────

    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    app.mount("/static", StaticFiles(directory=str(ui_dir)), name="static")

    # ── Agent listing router (GET /api/v1/agents) ────────────────────────
    
    app.include_router(agent_router)

    # ── WebSocket chat router ──────────────────────────────────────────────

    app.include_router(ws_router)

    # ── Serve the chat HTML page at / ──────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def chat_page():
        """Serve the single-page chat interface."""
        html_path = ui_dir / "chat.html"
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    # ── Health-check ───────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    return app
