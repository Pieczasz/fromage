from __future__ import annotations

import ipaddress
import re
import socket
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura

from fromage.models import Page

_MAX_BYTES = 5_000_000
_DEADLINE_S = 30.0
_MAX_REDIRECTS = 5
_CACHE_TTL_S = 24 * 3600
_FIGURE = re.compile(r"<(/?)figure\b", re.I)


def _validate_url(url: str) -> None:
    """Allow only http(s) URLs whose host resolves exclusively to public IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"cannot resolve host: {host}") from e
    # ponytail: DNS can change between this check and httpx's own lookup (rebinding); pin IPs if that matters
    for *_, sockaddr in infos:
        addr = ipaddress.ip_address(sockaddr[0])
        addr = getattr(addr, "ipv4_mapped", None) or addr
        if not addr.is_global:
            raise ValueError(f"blocked host address: {host} resolves to {addr}")


class HttpFetcher:
    def __init__(self, cache_path: str, *, client: httpx.Client | None = None) -> None:
        self._cache_path = Path(cache_path)
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = client
        self._init_cache()

    def _init_cache(self) -> None:
        with sqlite3.connect(self._cache_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS page_cache "
                "(url TEXT PRIMARY KEY, text TEXT NOT NULL, fetched_at REAL NOT NULL)"
            )

    def _cache_get(self, url: str) -> str | None:
        with sqlite3.connect(self._cache_path) as conn:
            row = conn.execute(
                "SELECT text FROM page_cache WHERE url = ? AND fetched_at > ?",
                (url, time.time() - _CACHE_TTL_S),
            ).fetchone()
        return row[0] if row else None

    def _cache_put(self, url: str, text: str) -> None:
        with sqlite3.connect(self._cache_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO page_cache (url, text, fetched_at) VALUES (?, ?, ?)",
                (url, text, time.time()),
            )

    def fetch(self, url: str) -> Page:
        _validate_url(url)
        cached = self._cache_get(url)
        if cached is not None:
            return Page(url=url, text=cached)

        own = self._client is None
        client = self._client or httpx.Client(timeout=15.0)
        try:
            html = self._get(client, url)
        finally:
            if own:
                client.close()

        text = self.extract_html(html, url=url)
        if text:  # never cache a failed extraction, so a retry can succeed
            self._cache_put(url, text)
        return Page(url=url, text=text)

    @staticmethod
    def _get(client: httpx.Client, url: str) -> str:
        """GET with every redirect hop re-validated, a size cap, and a total deadline."""
        deadline = time.monotonic() + _DEADLINE_S
        for _ in range(_MAX_REDIRECTS + 1):
            with client.stream(
                "GET",
                url,
                headers={"User-Agent": "fromage/0.1 (+local lab)"},
                follow_redirects=False,
            ) as r:
                if r.is_redirect:
                    url = str(r.url.join(r.headers["location"]))
                    _validate_url(url)
                    continue
                r.raise_for_status()
                body = bytearray()
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > _MAX_BYTES:
                        raise ValueError(f"response larger than {_MAX_BYTES} bytes")
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"fetch took longer than {_DEADLINE_S:.0f}s")
                return body.decode(r.encoding or "utf-8", errors="replace")
        raise ValueError(f"too many redirects (>{_MAX_REDIRECTS})")

    @staticmethod
    def extract_html(html: str, url: str = "") -> str:
        # Docs sites wrap code blocks in <figure>, which trafilatura discards as non-content.
        html = _FIGURE.sub(r"<\1div", html)
        return trafilatura.extract(html, url=url, output_format="markdown") or ""
