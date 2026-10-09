from __future__ import annotations

from fromage.embed_ollama import chunk_text, make_chunk_id
from fromage.models import Chunk, Hit, Page
from fromage.ports import Embed, Fetch, Memory, Search


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

    def _check_model(self) -> str:
        model = self._embed.model_id
        stored = self._memory.embed_model
        if stored and stored != model:
            raise RuntimeError(
                f"memory was built with embed model {stored!r} but FROMAGE_EMBED_MODEL is {model!r}; "
                "switch back or delete the memory database"
            )
        return model

    def search(self, query: str, mode: str = "general", limit: int = 8) -> list[Hit]:
        return self._search.search(query, mode=mode, limit=limit)

    def read(self, url: str) -> Page:
        return self._fetch.fetch(url)

    def remember(self, url: str) -> int:
        page = self._fetch.fetch(url)
        pieces = chunk_text(page.text)
        if not pieces:
            return 0
        model = self._check_model()
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
        model = self._check_model()
        qvec = self._embed.embed([query])[0]
        return self._memory.search(qvec, k=k)
