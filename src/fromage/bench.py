from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from fromage.metrics import mrr, recall_at_k
from fromage.models import Chunk
from fromage.ports import build_embed, build_memory, build_pipeline, build_search


@dataclass
class WebCase:
    query: str
    mode: str
    url_substrings: list[str]
    snippet_terms: list[str]
    tags: list[str] = field(default_factory=list)
    difficulty: str = "easy"
    id: str = ""
    topic: str = ""
    split: str = ""
    dup_of: str | None = None


@dataclass
class MemoryCase:
    query: str
    relevant_ids: list[str]
    text: str
    doc_id: str
    tags: list[str] = field(default_factory=list)
    difficulty: str = "easy"
    id: str = ""


def load_web(path: Path) -> list[WebCase]:
    cases: list[WebCase] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        cases.append(
            WebCase(
                id=o.get("id") or f"web-{i:03d}",
                query=o["query"],
                mode=o.get("mode", "general"),
                url_substrings=o.get("url_substrings", []),
                snippet_terms=o.get("snippet_terms", []),
                tags=o.get("tags", []),
                difficulty=o.get("difficulty", "easy"),
                topic=o.get("topic") or "",
                split=o.get("split") or "",
                dup_of=o.get("dup_of"),
            )
        )
    return cases


def load_memory(path: Path) -> list[MemoryCase]:
    cases: list[MemoryCase] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        cases.append(
            MemoryCase(
                id=o.get("id") or f"mem-{i:03d}",
                query=o["query"],
                relevant_ids=o["relevant_ids"],
                text=o["text"],
                doc_id=o["doc_id"],
                tags=o.get("tags", []),
                difficulty=o.get("difficulty", "easy"),
            )
        )
    return cases


def filter_split(cases: list[WebCase], split: str) -> list[WebCase]:
    if split in ("", "all"):
        return cases
    return [c for c in cases if c.split == split or (not c.split and split == "train")]


def web_hit(hits: list, case: WebCase, k: int = 5) -> bool:
    top = hits[:k]
    for h in top:
        url = h.url.lower()
        sn = (h.snippet + " " + h.title).lower()
        if any(sub.lower() in url for sub in case.url_substrings):
            return True
        if any(term.lower() in sn for term in case.snippet_terms):
            return True
    return False


def topical_hit(hits: list, case: WebCase, k: int = 5) -> bool:
    """True if any top-k result matches topic hosts or distinctive terms."""
    return web_hit(hits, case, k=k)


def _rate(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def build_topic_host_index(cases: list[WebCase]) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = defaultdict(set)
    for c in cases:
        if not c.topic:
            continue
        for h in c.url_substrings:
            idx[c.topic].add(h.lower())
    return idx


def topic_leakage(hits: list, case: WebCase, topic_hosts: dict[str, set[str]], k: int = 5) -> str | None:
    """If results match another topic's hosts more than own, return that topic name."""
    if not case.topic or case.topic not in topic_hosts:
        return None
    scores: dict[str, int] = defaultdict(int)
    for h in hits[:k]:
        host = _host(h.url)
        text = f"{h.url} {h.title} {h.snippet}".lower()
        for topic, hosts in topic_hosts.items():
            if any(s in host or s in text for s in hosts):
                scores[topic] += 1
    if not scores:
        return None
    best = max(scores, key=lambda t: scores[t])
    if best != case.topic and scores[best] > scores.get(case.topic, 0):
        return best
    return None


def run_web_bench(
    cases: list[WebCase],
    k: int = 5,
    *,
    delay_s: float = 0.0,
    all_cases_for_topics: list[WebCase] | None = None,
) -> dict[str, Any]:
    search = build_search()
    topic_hosts = build_topic_host_index(all_cases_for_topics or cases)
    by_mode: dict[str, list[bool]] = defaultdict(list)
    by_diff: dict[str, list[bool]] = defaultdict(list)
    by_tag: dict[str, list[bool]] = defaultdict(list)
    by_topic: dict[str, list[bool]] = defaultdict(list)
    by_split: dict[str, list[bool]] = defaultdict(list)
    latencies: list[float] = []
    empty = 0
    hits_n = 0
    topical_n = 0
    leaks: dict[str, int] = defaultdict(int)
    misses: list[dict[str, Any]] = []
    dup_pairs: list[tuple[str, str, bool, bool]] = []
    results_by_id: dict[str, list] = {}

    for idx, case in enumerate(cases, start=1):
        t0 = time.perf_counter()
        try:
            results = search.search(case.query, mode=case.mode, limit=max(8, k))
        except Exception as e:
            results = []
            empty += 1
            print(f"web error {case.mode} {case.query!r}: {e}", flush=True)
        dt = time.perf_counter() - t0
        latencies.append(dt)
        if not results:
            empty += 1
        ok = web_hit(results, case, k=k)
        top = topical_hit(results, case, k=k)
        hits_n += int(ok)
        topical_n += int(top)
        by_mode[case.mode].append(ok)
        by_diff[case.difficulty].append(ok)
        by_split[case.split or "unspecified"].append(ok)
        if case.topic:
            by_topic[case.topic].append(top)
        for tag in case.tags or ["untagged"]:
            by_tag[tag].append(ok)
        leak = topic_leakage(results, case, topic_hosts, k=k)
        if leak:
            leaks[f"{case.topic} to {leak}"] += 1
        results_by_id[case.id] = results
        if not ok:
            misses.append(
                {
                    "id": case.id,
                    "mode": case.mode,
                    "topic": case.topic,
                    "split": case.split,
                    "difficulty": case.difficulty,
                    "tags": case.tags,
                    "query": case.query,
                    "expected_urls": case.url_substrings,
                    "expected_terms": case.snippet_terms,
                    "leak_to": leak,
                    "top_urls": [h.url for h in results[:k]],
                    "top_titles": [h.title[:100] for h in results[:k]],
                }
            )
        if idx % 25 == 0 or idx == len(cases):
            print(
                f"  progress {idx}/{len(cases)} accuracy={hits_n/idx:.3f} "
                f"topical={topical_n/idx:.3f} empty={empty} last={dt:.2f}s",
                flush=True,
            )
        if delay_s > 0:
            time.sleep(delay_s)

    # Duplicate/paraphrase stability: same topical_hit outcome as parent when both evaluated
    id_ok = {c.id: web_hit(results_by_id.get(c.id, []), c, k=k) for c in cases if c.id in results_by_id}
    stable = 0
    unstable = 0
    for c in cases:
        if not c.dup_of or c.dup_of not in id_ok or c.id not in id_ok:
            continue
        same = id_ok[c.id] == id_ok[c.dup_of]
        dup_pairs.append((c.dup_of, c.id, id_ok[c.dup_of], id_ok[c.id]))
        if same:
            stable += 1
        else:
            unstable += 1

    n = len(cases) or 1
    return {
        "accuracy": hits_n / n,
        "topical_accuracy": topical_n / n,
        "count": len(cases),
        "k": k,
        "latency_avg_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "empty_results": empty,
        "by_mode": {m: {"accuracy": _rate(v), "count": len(v)} for m, v in sorted(by_mode.items())},
        "by_difficulty": {
            d: {"accuracy": _rate(v), "count": len(v)} for d, v in sorted(by_diff.items())
        },
        "by_topic": {
            t: {"topical_accuracy": _rate(v), "count": len(v)} for t, v in sorted(by_topic.items())
        },
        "by_split": {s: {"accuracy": _rate(v), "count": len(v)} for s, v in sorted(by_split.items())},
        "by_tag": {t: {"accuracy": _rate(v), "count": len(v)} for t, v in sorted(by_tag.items()) if t in (
            "duplicate", "paraphrase", "hard", "shared-lang", "cross-topic", "generated"
        ) or len(v) >= 5},
        "topic_leakage": dict(sorted(leaks.items(), key=lambda kv: -kv[1])[:30]),
        "dup_stability": {
            "pairs": stable + unstable,
            "stable_rate": stable / (stable + unstable) if (stable + unstable) else None,
            "unstable": unstable,
        },
        "misses": misses,
        "miss_count": len(misses),
    }


def run_memory_bench(cases: list[MemoryCase], k: int = 5) -> dict[str, Any]:
    embed = build_embed()
    memory = build_memory()
    memory.clear()
    model = embed.model_id

    seen: dict[str, MemoryCase] = {}
    for case in cases:
        if case.doc_id not in seen and case.text:
            seen[case.doc_id] = case
    chunks = [
        Chunk(id=c.doc_id, url=f"bench://{c.doc_id}", text=c.text, embed_model=model)
        for c in seen.values()
    ]
    vectors: list[list[float]] = []
    texts = [c.text for c in chunks]
    for i in range(0, len(texts), 16):
        vectors.extend(embed.embed(texts[i : i + 16]))
    memory.upsert(chunks, vectors)

    recall_scores: list[float] = []
    mrr_scores: list[float] = []
    by_diff: dict[str, list[float]] = defaultdict(list)
    by_tag: dict[str, list[float]] = defaultdict(list)
    misses: list[dict[str, Any]] = []
    for case in cases:
        qvec = embed.embed([case.query])[0]
        ranked = memory.search(qvec, k=k)
        ranked_ids = [c.id for c, _ in ranked]
        rel = set(case.relevant_ids)
        r = recall_at_k(ranked_ids, rel, k)
        m = mrr(ranked_ids, rel)
        recall_scores.append(r)
        mrr_scores.append(m)
        by_diff[case.difficulty].append(r)
        for tag in case.tags or ["untagged"]:
            by_tag[tag].append(r)
        if r < 1.0:
            misses.append(
                {
                    "id": case.id,
                    "difficulty": case.difficulty,
                    "tags": case.tags,
                    "query": case.query,
                    "relevant_ids": case.relevant_ids,
                    "ranked_ids": ranked_ids,
                    "recall_at_k": r,
                    "mrr": m,
                }
            )
    n = len(cases) or 1
    return {
        "recall_at_k": sum(recall_scores) / n,
        "mrr": sum(mrr_scores) / n,
        "k": k,
        "count": len(cases),
        "indexed_docs": len(chunks),
        "embed_model": model,
        "memory_backend": type(memory).__name__,
        "by_difficulty": {
            d: {"recall_at_k": sum(v) / len(v), "count": len(v)} for d, v in sorted(by_diff.items())
        },
        "by_tag": {
            t: {"recall_at_k": sum(v) / len(v), "count": len(v)} for t, v in sorted(by_tag.items())
        },
        "misses": misses,
        "miss_count": len(misses),
    }


def run_judge(sample: list[MemoryCase], host: str, model: str, n: int = 10) -> dict[str, Any]:
    pipe = build_pipeline()
    memory = build_memory()
    embed = build_embed()
    memory.clear()
    model_id = embed.model_id
    for case in sample[:n]:
        if not case.text:
            continue
        memory.upsert(
            [Chunk(id=case.doc_id, url="bench://", text=case.text, embed_model=model_id)],
            embed.embed([case.text]),
        )
    supported = 0
    tried = 0
    client = httpx.Client(timeout=120.0)
    try:
        for case in sample[:n]:
            rows = pipe.recall(case.query, k=3)
            context = "\n".join(c.text for c, _ in rows)
            prompt = (
                f"Context:\n{context}\n\nQuestion: {case.query}\n\n"
                "Is the context sufficient to answer correctly? Reply only YES or NO."
            )
            r = client.post(
                f"{host.rstrip('/')}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            ans = r.json().get("response", "").strip().upper()
            tried += 1
            if ans.startswith("YES"):
                supported += 1
    finally:
        client.close()
    return {
        "judge_model": model,
        "supported_rate": supported / tried if tried else 0.0,
        "count": tried,
        "note": "non-deterministic LLM judge",
    }


def _print_web_summary(label: str, report: dict[str, Any]) -> None:
    summary = {k: v for k, v in report.items() if k != "misses"}
    print(f"\n=== {label} ===")
    print(json.dumps(summary, indent=2))
    if report.get("misses"):
        print(f"\nMisses ({report['miss_count']}), showing up to 15:")
        for m in report["misses"][:15]:
            print(f"  [{m.get('topic')}/{m.get('split')}] {m['query']!r}")
            print(f"    got: {m['top_urls'][:3]}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Benchmark fromage web and memory layers")
    p.add_argument("--web", type=Path, default=Path("bench/web.jsonl"))
    p.add_argument("--memory", type=Path, default=Path("bench/memory.jsonl"))
    p.add_argument("--out-dir", type=Path, default=Path("bench/results"))
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--web-only", action="store_true")
    p.add_argument("--memory-only", action="store_true")
    p.add_argument(
        "--split",
        choices=["train", "test", "all", "both"],
        default="all",
        help="web split: train~90%%, test~10%%, both=run train then test separately",
    )
    p.add_argument("--delay", type=float, default=0.15, help="seconds between web queries (CAPTCHA hygiene)")
    p.add_argument("--limit", type=int, default=0, help="optional cap on cases after split (0=all)")
    p.add_argument("--judge", action="store_true")
    p.add_argument("--judge-model", default="qwen2.5:7b")
    args = p.parse_args(argv)

    web_all = load_web(args.web) if args.web.is_file() and not args.memory_only else []
    mem_cases = load_memory(args.memory) if args.memory.is_file() and not args.web_only else []

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "web": None,
        "web_train": None,
        "web_test": None,
        "memory": None,
        "judge": None,
    }

    def run_web(split_name: str) -> dict[str, Any]:
        cases = filter_split(web_all, split_name if split_name != "all" else "all")
        if args.limit > 0:
            cases = cases[: args.limit]
        print(f"Running web bench ({len(cases)} cases, split={split_name})...")
        return run_web_bench(
            cases, k=args.k, delay_s=args.delay, all_cases_for_topics=web_all or cases
        )

    if web_all:
        if args.split == "both":
            # Held-out test first so we see generalization before the long train pass.
            report["web_test"] = run_web("test")
            _print_web_summary("TEST (held out)", report["web_test"])
            report["web_train"] = run_web("train")
            _print_web_summary("TRAIN", report["web_train"])
            tr = report["web_train"]["topical_accuracy"]
            te = report["web_test"]["topical_accuracy"]
            report["web"] = {
                "train_topical_accuracy": tr,
                "test_topical_accuracy": te,
                "train_accuracy": report["web_train"]["accuracy"],
                "test_accuracy": report["web_test"]["accuracy"],
                "generalization_gap": tr - te,
                "note": "Tune only on train; test is held out. Large positive gap => overfitting risk.",
            }
            print(json.dumps(report["web"], indent=2), flush=True)
        else:
            report["web"] = run_web(args.split)
            _print_web_summary(args.split.upper(), report["web"])
    elif not args.memory_only:
        print(f"No web cases at {args.web}")

    if mem_cases:
        print(f"Running memory bench ({len(mem_cases)} cases)...")
        report["memory"] = run_memory_bench(mem_cases, k=args.k)
        summary = {k: v for k, v in report["memory"].items() if k != "misses"}
        print(json.dumps(summary, indent=2))
    elif not args.web_only:
        print(f"No memory cases at {args.memory}")

    if args.judge and mem_cases:
        host = __import__("os").environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        report["judge"] = run_judge(mem_cases, host, args.judge_model)
        print(json.dumps(report["judge"], indent=2))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out_dir / f"{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
