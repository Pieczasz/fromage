from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fromage.models import Chunk
from fromage.rank import cosine


class SQLiteMemory:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embed_model TEXT NOT NULL,
                    vector_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_model ON chunks(embed_model)"
            )

    @property
    def embed_model(self) -> str | None:
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                "SELECT embed_model FROM chunks LIMIT 1"
            ).fetchone()
        return row[0] if row else None

    def clear(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute("DELETE FROM chunks")

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        with sqlite3.connect(self._path) as conn:
            for chunk, vec in zip(chunks, vectors):
                model = chunk.embed_model or ""
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chunks (id, url, text, embed_model, vector_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk.id, chunk.url, chunk.text, model, json.dumps(vec)),
                )

    def search(self, vector: list[float], k: int = 5) -> list[tuple[Chunk, float]]:
        rows: list[tuple[str, str, str, str, str]] = []
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                "SELECT id, url, text, embed_model, vector_json FROM chunks"
            ).fetchall()
        scored: list[tuple[Chunk, float]] = []
        for cid, url, text, model, vec_json in rows:
            vec = json.loads(vec_json)
            score = cosine(vector, vec)
            scored.append(
                (
                    Chunk(id=cid, url=url, text=text, embed_model=model),
                    score,
                )
            )
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
