from __future__ import annotations

import httpx

from fromage.models import Chunk


class OllamaEmbed:
    def __init__(self, host: str, model: str, *, client: httpx.Client | None = None) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._client = client

    @property
    def model_id(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        own = self._client is None
        client = self._client or httpx.Client(timeout=120.0)
        try:
            r = client.post(
                f"{self._host}/api/embed",
                json={"model": self._model, "input": texts},
            )
            r.raise_for_status()
            data = r.json()
        finally:
            if own:
                client.close()
        embeddings = data.get("embeddings")
        if not embeddings:
            # older single-input shape
            emb = data.get("embedding")
            if emb is not None:
                return [emb]
            raise RuntimeError(f"Ollama embed returned no vectors: {data!r}")
        return [list(map(float, v)) for v in embeddings]


def chunk_text(text: str, size: int = 1000, overlap: int = 100) -> list[str]:
    if not text:
        return []
    if overlap >= size:
        overlap = max(0, size // 10)
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = end - overlap
    return chunks


def make_chunk_id(url: str, index: int) -> str:
    return f"{url}#{index}"
