"""MCP server exposing a `fetch_url` tool over Streamable HTTP."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

try:
    from .fetcher import fetch_page
except ImportError:
    from fetcher import fetch_page  # type: ignore[no-redef]


HOST = os.getenv("FASTMCP_HOST", "0.0.0.0")
# PORT is injected by Cloud Run; FASTMCP_PORT is the local fallback.
PORT = int(os.getenv("PORT") or os.getenv("FASTMCP_PORT", "8765"))

mcp = FastMCP(
    "web-fetch",
    instructions="Fetches a web page and returns cleaned text + metadata. Use to read URLs.",
    host=HOST,
    port=PORT,
)


@mcp.tool()
async def fetch_url(url: str, raw: bool = False) -> dict:
    """Fetch a web page and return its cleaned text content with metadata.

    Args:
        url: The http(s) URL to fetch. Private and loopback addresses are refused.
        raw: When true, return the raw response body as a string (HTML, JSON, etc.)
             instead of extracting the main article text.

    Returns:
        A dict with `url`, `content_type`, `size_bytes`, plus either `title`+`text`
        (default) or `content` (raw=True). On failure, returns `{"url": ..., "error": ...}`.
    """
    return await fetch_page(url, raw=raw)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
