from __future__ import annotations

import functools
import logging
import os
import sys
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from fromage.ports import build_pipeline

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("fromage.mcp")

mcp = MCPServer("fromage")
_pipeline = None


def _pipe():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


def _agent_errors(fn):
    """Turn expected failures into ToolErrors so the agent sees why, not just that, a call failed."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, RuntimeError, TimeoutError, httpx.HTTPError) as e:
            raise ToolError(str(e).splitlines()[0] or type(e).__name__) from e

    return wrapper


@mcp.tool()
@_agent_errors
def search(query: str, mode: str = "general", limit: int = 8) -> list[dict[str, str]]:
    """Search the web via local SearXNG. mode: general, academic, code, or news."""
    hits = _pipe().search(query, mode=mode, limit=limit)
    return [{"title": h.title, "url": h.url, "snippet": h.snippet} for h in hits]


@mcp.tool()
@_agent_errors
def read(url: str, max_chars: int = 20000, start: int = 0) -> dict[str, Any]:
    """Fetch a URL and return its main content as markdown (cached for 24h).

    Long pages come back in slices: if next_start is set, call again with start=next_start.
    """
    text = _pipe().read(url).text
    piece = text[start : start + max_chars]
    end = start + len(piece)
    return {
        "url": url,
        "text": piece,
        "total_chars": len(text),
        "next_start": end if end < len(text) else None,
    }


@mcp.tool()
@_agent_errors
def remember(url: str) -> dict[str, Any]:
    """Fetch a URL, chunk it, embed it, and store it in local memory for recall."""
    n = _pipe().remember(url)
    return {"url": url, "chunks_stored": n}


@mcp.tool()
@_agent_errors
def recall(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Return the k stored memory chunks most similar to the query."""
    rows = _pipe().recall(query, k=k)
    return [
        {"id": c.id, "url": c.url, "text": c.text, "score": score} for c, score in rows
    ]


def main() -> None:
    transport = (os.environ.get("MCP_TRANSPORT") or "stdio").strip().lower()
    if transport in ("http", "streamable-http", "sse"):
        port = int(os.environ.get("MCP_PORT", "8765"))
        log.info("MCP listening on 0.0.0.0:%s (%s)", port, transport)
        mcp.run(
            transport="streamable-http" if transport != "sse" else "sse",
            host="0.0.0.0",
            port=port,
            json_response=True,
            stateless_http=True,
        )
        return
    mcp.run()


if __name__ == "__main__":
    main()
