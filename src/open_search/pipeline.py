from __future__ import annotations

from open_search.embed_ollama import chunk_text, make_chunk_id
from open_search.models import Chunk, Hit, Page
from open_search.ports import Embed, Fetch, Memory, Search


class Pipeline:
    def __init__(
        self,
        search: Search,
        fetch: Fetch,
        embed: Embed,
        memory: Memory,
    ) -> None:
        self._search = search
        self._fetch = fetch
        self._embed = embed
        self._memory = memory

    def search(self, query: str, mode: str = "general", limit: int = 8) -> list[Hit]:
        return self._search.search(query, mode=mode, limit=limit)

    def read(self, url: str) -> Page:
        return self._fetch.fetch(url)

    def remember(self, url: str) -> int:
        page = self._fetch.fetch(url)
        pieces = chunk_text(page.text)
        if not pieces:
            return 0
        model = self._embed.model_id
        stored = self._memory.embed_model
        if stored and stored != model:
            raise RuntimeError(
                f"embed model mismatch: memory has {stored!r}, current is {model!r}; run reindex first"
            )
        chunks = [
            Chunk(
                id=make_chunk_id(url, i),
                url=url,
                text=t,
                embed_model=model,
            )
            for i, t in enumerate(pieces)
        ]
        vectors = self._embed.embed([c.text for c in chunks])
        self._memory.upsert(chunks, vectors)
        return len(chunks)

    def recall(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        model = self._embed.model_id
        stored = self._memory.embed_model
        if stored and stored != model:
            raise RuntimeError(
                f"embed model mismatch: memory has {stored!r}, current is {model!r}; run reindex first"
            )
        qvec = self._embed.embed([query])[0]
        return self._memory.search(qvec, k=k)

    def reindex(self) -> int:
        """Re-embed all stored chunk text with the current embed model."""
        # ponytail: only SQLite exposes list-all; Qdrant reindex clears and needs URLs re-fetched
        if not hasattr(self._memory, "all_chunks"):
            raise RuntimeError("reindex from stored text is only supported for sqlite memory")
        from open_search.memory_sqlite import SQLiteMemory

        if not isinstance(self._memory, SQLiteMemory):
            raise RuntimeError("reindex from stored text is only supported for sqlite memory")
        rows = self._memory.all_chunks()
        if not rows:
            return 0
        model = self._embed.model_id
        chunks = [
            Chunk(id=cid, url=url, text=text, embed_model=model) for cid, url, text in rows
        ]
        vectors = self._embed.embed([c.text for c in chunks])
        self._memory.clear()
        self._memory.upsert(chunks, vectors)
        return len(chunks)
