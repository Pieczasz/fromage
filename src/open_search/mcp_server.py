from __future__ import annotations

import logging
import os
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from open_search.ports import build_pipeline

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("open_search.mcp")

mcp = MCPServer("open-search")
_pipeline = None


def _pipe():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


@mcp.tool()
def search(query: str, mode: str = "general", limit: int = 8) -> list[dict[str, str]]:
    """Search the web via local SearXNG (mode: general, academic, code, news)."""
    hits = _pipe().search(query, mode=mode, limit=limit)
    return [{"title": h.title, "url": h.url, "snippet": h.snippet} for h in hits]


@mcp.tool()
def read(url: str) -> dict[str, Any]:
    """Fetch a URL and return extracted main text (cached)."""
    page = _pipe().read(url)
    return {"url": page.url, "text": page.text, "length": len(page.text)}


@mcp.tool()
def remember(url: str) -> dict[str, Any]:
    """Fetch URL, chunk, embed, and store in memory."""
    n = _pipe().remember(url)
    return {"url": url, "chunks_stored": n}


@mcp.tool()
def recall(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Retrieve nearest memory chunks for a query."""
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
