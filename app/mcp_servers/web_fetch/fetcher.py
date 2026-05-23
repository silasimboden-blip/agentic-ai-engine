"""Web page fetcher with cleaned-text extraction and basic SSRF protection."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from readability import Document

USER_AGENT = "agentic-ai-engine/web-fetch (+https://github.com/silasimboden-blip/agentic-ai-engine)"
TIMEOUT_SECONDS = 10.0
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5


class FetchError(Exception):
    """Raised when a fetch is refused or fails."""


def _validate_url(url: str) -> str:
    """Return the validated URL string or raise FetchError.

    Blocks non-http(s) schemes and hostnames that resolve to private,
    loopback, link-local, reserved, multicast, or unspecified addresses
    to prevent server-side request forgery against internal services.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"Only http and https URLs are allowed (got {parsed.scheme!r}).")
    host = parsed.hostname
    if not host:
        raise FetchError("URL must include a hostname.")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise FetchError(f"DNS resolution failed for {host!r}: {exc}") from exc
    for info in infos:
        ip_str = info[4][0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise FetchError(f"Refusing to fetch internal address {ip_str} for host {host!r}.")
    return url


async def _download(url: str) -> tuple[bytes, str, str, str]:
    """Stream-download the URL with size + redirect caps. Returns (content, content_type, final_url, encoding)."""
    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            buf = bytearray()
            async for chunk in response.aiter_bytes():
                if len(buf) + len(chunk) > MAX_BYTES:
                    raise FetchError(f"Response exceeds {MAX_BYTES} byte limit.")
                buf.extend(chunk)
            return bytes(buf), response.headers.get("content-type", ""), str(response.url), response.encoding or "utf-8"


def _extract_text(html: str) -> tuple[str, str]:
    """Return (title, cleaned_text) extracted from HTML using readability + BeautifulSoup."""
    doc = Document(html)
    title = (doc.title() or "").strip()
    summary_html = doc.summary()
    soup = BeautifulSoup(summary_html, "lxml")
    text = soup.get_text(separator="\n", strip=True)
    return title, text


async def fetch_page(url: str, raw: bool = False) -> dict:
    """Fetch a web page and return either cleaned text + metadata, or raw content."""
    try:
        validated = _validate_url(url)
        content, content_type, final_url, encoding = await _download(validated)
    except FetchError as exc:
        return {"url": url, "error": str(exc)}
    except httpx.HTTPError as exc:
        return {"url": url, "error": f"HTTP error: {exc}"}

    ct = content_type.lower()
    size = len(content)

    if raw:
        if "html" in ct or "text/" in ct or "json" in ct or "xml" in ct:
            return {
                "url": final_url,
                "content_type": content_type,
                "size_bytes": size,
                "content": content.decode(encoding, errors="replace"),
            }
        return {
            "url": final_url,
            "content_type": content_type,
            "size_bytes": size,
            "content": "<binary content; raw mode does not return bytes>",
        }

    if "html" in ct:
        html = content.decode(encoding, errors="replace")
        try:
            title, text = _extract_text(html)
        except Exception as exc:
            soup = BeautifulSoup(html, "lxml")
            return {
                "url": final_url,
                "content_type": content_type,
                "size_bytes": size,
                "title": (soup.title.string.strip() if soup.title and soup.title.string else ""),
                "text": soup.get_text(separator="\n", strip=True),
                "warning": f"readability extraction failed: {exc}",
            }
        return {
            "url": final_url,
            "content_type": content_type,
            "size_bytes": size,
            "title": title,
            "text": text,
        }

    if "text/" in ct or "json" in ct or "xml" in ct:
        return {
            "url": final_url,
            "content_type": content_type,
            "size_bytes": size,
            "text": content.decode(encoding, errors="replace"),
        }

    return {
        "url": final_url,
        "content_type": content_type,
        "size_bytes": size,
        "text": f"<binary content of type {content_type or 'unknown'}; pass raw=True for full bytes-as-string view>",
    }
