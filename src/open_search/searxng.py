from __future__ import annotations

import httpx

from open_search.models import Hit
from open_search.modes import get_mode
from open_search.ports import Embed
from open_search.rank import (
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
        if not self._improve:
            return self._search_once(query, mode, limit=limit)[:limit]

        cfg = get_mode(mode)
        queries = rewrite_queries(query, mode)
        pool: list[Hit] = []
        seen_urls: set[str] = set()

        fetch_n = max(limit * 3, 15)
        for i, q in enumerate(queries):
            engines = engines_for_mode(mode, q, cfg.get("engines"))
            categories = cfg["categories"]
            if i > 0 and mode == "code":
                categories = "general"
                engines = engines_for_mode("code", q, "yep,duckduckgo,brave,github,stackoverflow")
            batch = self._search_once(
                q, mode, limit=fetch_n, categories=categories, engines=engines
            )
            for h in batch:
                if h.url in seen_urls:
                    continue
                seen_urls.add(h.url)
                pool.append(h)

        # Prefer general web for conceptual code queries (IT category is package-heavy)
        if mode == "code":
            batch = self._search_once(
                queries[0],
                mode,
                limit=fetch_n,
                categories="general",
                engines="yep,duckduckgo,brave",
            )
            for h in batch:
                if h.url not in seen_urls:
                    seen_urls.add(h.url)
                    pool.append(h)

        semantics = self._semantic_scores(query, pool) if self._semantic else None
        # Soft gates: never drop the whole pool if upstream is sparse
        return rerank(
            pool,
            query,
            mode,
            limit,
            semantics=semantics,
            min_overlap=0.0,
            min_semantic=0.0,
        )

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
        self,
        query: str,
        mode: str,
        *,
        limit: int,
        categories: str | None = None,
        engines: str | None = None,
    ) -> list[Hit]:
        cfg = get_mode(mode)
        params: dict[str, str | int] = {
            "q": query,
            "format": "json",
            "categories": categories or cfg["categories"],
        }
        eng = engines if engines is not None else cfg.get("engines")
        if eng:
            params["engines"] = eng
        if cfg.get("time_range"):
            params["time_range"] = cfg["time_range"]

        own = self._client is None
        client = self._client or httpx.Client(timeout=30.0)
        try:
            r = client.get(f"{self._base}/search", params=params)
            r.raise_for_status()
            data = r.json()
        finally:
            if own:
                client.close()

        return self.parse_results(data, limit=limit)

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
