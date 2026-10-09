from __future__ import annotations


def hit_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> bool:
    return bool(relevant.intersection(ranked_ids[:k]))


def recall_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = len(relevant.intersection(ranked_ids[:k]))
    return hits / len(relevant)


def mrr(ranked_ids: list[str], relevant: set[str]) -> float:
    for i, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0
