from __future__ import annotations

import ipaddress
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura

from open_search.models import Page

_BLOCKED_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme: {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL has no host")
    if host in _BLOCKED_HOSTS or host.endswith(".internal"):
        raise ValueError(f"blocked host: {host}")
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError(f"blocked host address: {host}")
    except ValueError as e:
        if "blocked" in str(e):
            raise
        # hostname, not literal IP; allow public DNS names


class HttpFetcher:
    def __init__(self, cache_path: str, *, client: httpx.Client | None = None) -> None:
        self._cache_path = Path(cache_path)
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = client
        self._init_cache()

    def _init_cache(self) -> None:
        with sqlite3.connect(self._cache_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS pages (url TEXT PRIMARY KEY, text TEXT NOT NULL)"
            )

    def _cache_get(self, url: str) -> str | None:
        with sqlite3.connect(self._cache_path) as conn:
            row = conn.execute("SELECT text FROM pages WHERE url = ?", (url,)).fetchone()
        return row[0] if row else None

    def _cache_put(self, url: str, text: str) -> None:
        with sqlite3.connect(self._cache_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pages (url, text) VALUES (?, ?)", (url, text)
            )

    def fetch(self, url: str) -> Page:
        _validate_url(url)
        cached = self._cache_get(url)
        if cached is not None:
            return Page(url=url, text=cached)

        own = self._client is None
        client = self._client or httpx.Client(timeout=45.0, follow_redirects=True)
        try:
            r = client.get(url, headers={"User-Agent": "open-search/0.1 (+local lab)"})
            r.raise_for_status()
            html = r.text
        finally:
            if own:
                client.close()

        text = trafilatura.extract(html, url=url) or ""
        self._cache_put(url, text)
        return Page(url=url, text=text)

    @staticmethod
    def extract_html(html: str, url: str = "") -> str:
        return trafilatura.extract(html, url=url) or ""
