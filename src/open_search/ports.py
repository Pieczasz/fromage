from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from open_search.models import Chunk, Hit, Page


@runtime_checkable
class Search(Protocol):
    def search(self, query: str, mode: str = "general", limit: int = 8) -> list[Hit]: ...


@runtime_checkable
class Fetch(Protocol):
    def fetch(self, url: str) -> Page: ...


@runtime_checkable
class Embed(Protocol):
    @property
    def model_id(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class Memory(Protocol):
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

    def search(self, vector: list[float], k: int = 5) -> list[tuple[Chunk, float]]: ...

    def clear(self) -> None: ...

    @property
    def embed_model(self) -> str | None: ...


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def build_search() -> Search:
    from open_search.searxng import SearXNGSearch

    base = env("OPEN_SEARCH_SEARXNG_URL", "http://127.0.0.1:8888") or "http://127.0.0.1:8888"
    improve = (env("OPEN_SEARCH_IMPROVE", "1") or "1") not in ("0", "false", "False")
    semantic = (env("OPEN_SEARCH_SEMANTIC_RERANK", "1") or "1") not in ("0", "false", "False")
    embed = None
    if improve and semantic:
        try:
            embed = build_embed()
        except Exception:
            embed = None
    return SearXNGSearch(
        base_url=base.rstrip("/"),
        improve=improve,
        embed=embed,
        semantic=semantic and embed is not None,
    )


def build_fetch() -> Fetch:
    from open_search.fetch import HttpFetcher

    cache = env("OPEN_SEARCH_PAGE_CACHE", ".data/pages.db") or ".data/pages.db"
    return HttpFetcher(cache_path=cache)


def build_embed() -> Embed:
    from open_search.embed_ollama import OllamaEmbed

    host = env("OLLAMA_HOST", "http://127.0.0.1:11434") or "http://127.0.0.1:11434"
    model = env("OPEN_SEARCH_EMBED_MODEL", "nomic-embed-text") or "nomic-embed-text"
    return OllamaEmbed(host=host.rstrip("/"), model=model)


def build_memory() -> Memory:
    backend = (env("OPEN_SEARCH_MEMORY", "sqlite") or "sqlite").lower()
    if backend == "sqlite":
        from open_search.memory_sqlite import SQLiteMemory

        path = env("OPEN_SEARCH_SQLITE_PATH", ".data/memory.db") or ".data/memory.db"
        return SQLiteMemory(path=path)
    if backend == "qdrant":
        from open_search.memory_qdrant import QdrantMemory

        url = env("OPEN_SEARCH_QDRANT_URL", "http://127.0.0.1:6333") or "http://127.0.0.1:6333"
        embed = build_embed()
        return QdrantMemory(url=url, collection_prefix="open_search", embed_model=embed.model_id)
    raise ValueError(f"unknown OPEN_SEARCH_MEMORY={backend!r}; use sqlite or qdrant")


def build_pipeline():
    from open_search.pipeline import Pipeline

    return Pipeline(
        search=build_search(),
        fetch=build_fetch(),
        embed=build_embed(),
        memory=build_memory(),
    )
