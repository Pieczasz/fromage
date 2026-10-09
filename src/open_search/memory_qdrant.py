from __future__ import annotations

import re
import uuid

from open_search.models import Chunk

_COLLECTION_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


class QdrantMemory:
    def __init__(self, url: str, embed_model: str, collection_prefix: str = "open_search") -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qm
        except ImportError as e:
            raise ImportError(
                "qdrant-client is required for OPEN_SEARCH_MEMORY=qdrant; "
                "install with: pip install open-search[qdrant]"
            ) from e
        self._qm = qm
        self._client = QdrantClient(url=url)
        safe = _COLLECTION_SAFE.sub("_", embed_model).strip("_")[:60]
        self._collection = f"{collection_prefix}_{safe}"
        self._embed_model = embed_model

    def _exists(self) -> bool:
        return self._client.collection_exists(self._collection)

    @property
    def embed_model(self) -> str | None:
        return self._embed_model

    def clear(self) -> None:
        if self._exists():
            self._client.delete_collection(self._collection)

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        if not vectors:
            return
        if not self._exists():
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=self._qm.VectorParams(
                    size=len(vectors[0]), distance=self._qm.Distance.COSINE
                ),
            )
        qm = self._qm
        points = []
        for chunk, vec in zip(chunks, vectors):
            points.append(
                qm.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.id)),
                    vector=vec,
                    payload={
                        "chunk_id": chunk.id,
                        "url": chunk.url,
                        "text": chunk.text,
                        "embed_model": chunk.embed_model or self._embed_model,
                    },
                )
            )
        self._client.upsert(collection_name=self._collection, points=points)

    def search(self, vector: list[float], k: int = 5) -> list[tuple[Chunk, float]]:
        if not self._exists():
            return []
        hits = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=k,
        ).points
        out: list[tuple[Chunk, float]] = []
        for hit in hits:
            p = hit.payload or {}
            out.append(
                (
                    Chunk(
                        id=str(p.get("chunk_id", "")),
                        url=str(p.get("url", "")),
                        text=str(p.get("text", "")),
                        embed_model=str(p.get("embed_model", "")),
                    ),
                    float(hit.score),
                )
            )
        return out
