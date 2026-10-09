from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx

from fromage.models import Hit
from fromage.modes import get_mode
from fromage.ports import Embed
from fromage.rank import (
    engines_for_mode,
    hit_text_for_embed,
    rerank,
    rewrite_queries,
    cosine,
)


class SearXNGSearch:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        improve: bool = True,
        embed: Embed | None = None,
        semantic: bool = True,
    ) -> None:
        self._base = base_url
        self._client = client
        self._improve = improve
        self._embed = embed
        self._semantic = semantic

    def search(self, query: str, mode: str = "general", limit: int = 8) -> list[Hit]:
        cfg = get_mode(mode)
        if not self._improve:
            return self._search_many([(query, cfg.get("engines"))], mode, limit=limit)[:limit]

        jobs = [(q, engines_for_mode(mode, q, cfg.get("engines"))) for q in rewrite_queries(query, mode)]
        pool = self._search_many(jobs, mode, limit=max(limit * 3, 15))
        semantics = self._semantic_scores(query, pool) if self._semantic else None
        return rerank(pool, query, mode, limit, semantics=semantics)

    def _search_many(self, jobs: list[tuple[str, str | None]], mode: str, *, limit: int) -> list[Hit]:
        """Run queries in parallel; keep whatever succeeds, fail only if every query fails."""
        own = self._client is None
        client = self._client or httpx.Client(timeout=15.0)
        try:
            with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
                futures = [
                    ex.submit(self._search_once, q, mode, limit=limit, engines=eng, client=client)
                    for q, eng in jobs
                ]
            batches, errors, failing = [], [], set()
            for f in futures:
                try:
                    hits, down = f.result()
                    batches.append(hits)
                    failing.update(down)
                except Exception as e:
                    errors.append(e)
        finally:
            if own:
                client.close()
        if not batches:
            raise errors[0]
        pool: list[Hit] = []
        seen: set[str] = set()
        for batch in batches:
            for h in batch:
                if h.url not in seen:
                    seen.add(h.url)
                    pool.append(h)
        if not pool and failing:
            # Tell the agent why, instead of an empty list it cannot act on.
            raise RuntimeError(f"no results; upstream engines failing: {', '.join(sorted(failing))}")
        return pool

    def _semantic_scores(self, query: str, hits: list[Hit]) -> list[float] | None:
        if not hits or self._embed is None:
            return None
        try:
            texts = [query] + [hit_text_for_embed(h) for h in hits]
            # Batch in chunks: Ollama handles multi-input
            vectors = self._embed.embed(texts)
            if len(vectors) != len(texts):
                return None
            qv = vectors[0]
            return [cosine(qv, v) for v in vectors[1:]]
        except Exception:
            return None

    def _search_once(
        self, query: str, mode: str, *, limit: int, engines: str | None, client: httpx.Client
    ) -> tuple[list[Hit], list[str]]:
        cfg = get_mode(mode)
        params: dict[str, str | int] = {"q": query, "format": "json", "categories": cfg["categories"]}
        if engines:
            params["engines"] = engines
        if cfg.get("time_range"):
            params["time_range"] = cfg["time_range"]
        r = client.get(f"{self._base}/search", params=params)
        r.raise_for_status()
        data = r.json()
        down = [f"{name} ({reason})" for name, reason in data.get("unresponsive_engines", [])]
        return self.parse_results(data, limit=limit), down

    @staticmethod
    def parse_results(data: dict, limit: int = 8) -> list[Hit]:
        hits: list[Hit] = []
        for item in data.get("results", [])[:limit]:
            hits.append(
                Hit(
                    title=str(item.get("title") or ""),
                    url=str(item.get("url") or ""),
                    snippet=str(item.get("content") or item.get("snippet") or ""),
                )
            )
        return hits
