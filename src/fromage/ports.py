from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from fromage.models import Chunk, Hit, Page


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
    from fromage.searxng import SearXNGSearch

    base = env("FROMAGE_SEARXNG_URL", "http://127.0.0.1:8888") or "http://127.0.0.1:8888"
    improve = (env("FROMAGE_IMPROVE", "1") or "1") not in ("0", "false", "False")
    semantic = (env("FROMAGE_SEMANTIC_RERANK", "1") or "1") not in ("0", "false", "False")
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
    from fromage.fetch import HttpFetcher

    cache = env("FROMAGE_PAGE_CACHE", ".data/pages.db") or ".data/pages.db"
    return HttpFetcher(cache_path=cache)


def build_embed() -> Embed:
    from fromage.embed_ollama import OllamaEmbed

    host = env("OLLAMA_HOST", "http://127.0.0.1:11434") or "http://127.0.0.1:11434"
    model = env("FROMAGE_EMBED_MODEL", "nomic-embed-text") or "nomic-embed-text"
    return OllamaEmbed(host=host.rstrip("/"), model=model)


def build_memory() -> Memory:
    backend = (env("FROMAGE_MEMORY", "sqlite") or "sqlite").lower()
    if backend == "sqlite":
        from fromage.memory_sqlite import SQLiteMemory

        path = env("FROMAGE_SQLITE_PATH", ".data/memory.db") or ".data/memory.db"
        return SQLiteMemory(path=path)
    if backend == "qdrant":
        from fromage.memory_qdrant import QdrantMemory

        url = env("FROMAGE_QDRANT_URL", "http://127.0.0.1:6333") or "http://127.0.0.1:6333"
        embed = build_embed()
        return QdrantMemory(url=url, collection_prefix="fromage", embed_model=embed.model_id)
    raise ValueError(f"unknown FROMAGE_MEMORY={backend!r}; use sqlite or qdrant")


def build_pipeline():
    from fromage.pipeline import Pipeline

    return Pipeline(
        search=build_search(),
        fetch=build_fetch(),
        embed=build_embed(),
        memory=build_memory(),
    )
