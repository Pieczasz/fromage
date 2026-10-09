from __future__ import annotations

import os

import pytest

from open_search.memory_sqlite import SQLiteMemory
from open_search.models import Chunk


class FakeEmbed:
    model_id = "fake-768"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            # deterministic 3-d vector from text hash for tests
            h = hash(t) % 1000
            out.append([float(h), float(h // 10), float(h // 100)])
        return out


@pytest.fixture
def sqlite_mem(tmp_path):
    return SQLiteMemory(str(tmp_path / "mem.db"))


def test_sqlite_recall_nearest(sqlite_mem: SQLiteMemory):
    embed = FakeEmbed()
    chunks = [
        Chunk(id="a#0", url="https://a", text="apple banana", embed_model=embed.model_id),
        Chunk(id="b#0", url="https://b", text="zebra yawn", embed_model=embed.model_id),
    ]
    vectors = embed.embed([c.text for c in chunks])
    sqlite_mem.upsert(chunks, vectors)
    q = embed.embed(["apple"])[0]
    results = sqlite_mem.search(q, k=1)
    assert results[0][0].id == "a#0"


def test_qdrant_same_nearest_if_available(tmp_path):
    if not os.environ.get("OPEN_SEARCH_QDRANT_URL"):
        pytest.skip("OPEN_SEARCH_QDRANT_URL not set")
    from open_search.memory_qdrant import QdrantMemory

    embed = FakeEmbed()
    mem = QdrantMemory(
        url=os.environ["OPEN_SEARCH_QDRANT_URL"],
        embed_model=embed.model_id,
        collection_prefix=f"test_{tmp_path.name}",
    )
    mem.clear()
    chunks = [
        Chunk(id="a#0", url="https://a", text="apple banana", embed_model=embed.model_id),
        Chunk(id="b#0", url="https://b", text="zebra yawn", embed_model=embed.model_id),
    ]
    vectors = embed.embed([c.text for c in chunks])
    mem.upsert(chunks, vectors)
    q = embed.embed(["apple"])[0]
    results = mem.search(q, k=1)
    assert results[0][0].id == "a#0"
    mem.clear()
