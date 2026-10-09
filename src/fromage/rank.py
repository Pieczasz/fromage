from __future__ import annotations

import math
import re
from urllib.parse import urlparse

from fromage.models import Hit

# Documentation / reference hosts (not package registries).
_DOC_HOST_SUFFIXES = (
    "readthedocs.io",
    "readthedocs.org",
    "github.io",
    "gitlab.io",
    "wikipedia.org",
    "arxiv.org",
    "ietf.org",
    "w3.org",
    "iana.org",
    "kernel.org",
    "gnu.org",
    "apache.org",
    "eclipse.org",
    "jetbrains.com",
)

_DOC_HOST_EXACT = frozenset(
    {
        "docs.python.org",
        "docs.djangoproject.com",
        "docs.pytest.org",
        "docs.github.com",
        "docs.docker.com",
        "docs.aws.amazon.com",
        "docs.microsoft.com",
        "learn.microsoft.com",
        "developer.mozilla.org",
        "react.dev",
        "nextjs.org",
        "nodejs.org",
        "typescriptlang.org",
        "go.dev",
        "pkg.go.dev",
        "doc.rust-lang.org",
        "rust-lang.org",
        "kubernetes.io",
        "prometheus.io",
        "opentelemetry.io",
        "sqlalchemy.org",
        "www.postgresql.org",
        "postgresql.org",
        "redis.io",
        "nginx.org",
        "nginx.com",
        "git-scm.com",
        "webpack.js.org",
        "vitejs.dev",
        "vuejs.org",
        "angular.io",
        "svelte.dev",
        "fastapi.tiangolo.com",
        "flask.palletsprojects.com",
        "numpy.org",
        "pandas.pydata.org",
        "pytorch.org",
        "tensorflow.org",
        "huggingface.co",
        "registry.terraform.io",
        "developer.hashicorp.com",
        "swagger.io",
        "openapi.org",
        "graphql.org",
        "stackoverflow.com",
        "serverfault.com",
        "askubuntu.com",
        "superuser.com",
        "stackexchange.com",
        "devblogs.microsoft.com",
        "martinfowler.com",
        "realpython.com",
        "css-tricks.com",
        "web.dev",
        "developer.chrome.com",
        "android.com",
        "developer.apple.com",
        "swift.org",
        "kotlinlang.org",
        "ruby-lang.org",
        "php.net",
        "perl.org",
        "haskell.org",
        "hackage.haskell.org",
        "cppreference.com",
        "en.cppreference.com",
        "man7.org",
        "linux.die.net",
        "tldp.org",
        "helm.sh",
        "grafana.com",
        "jaegertracing.io",
        "cncf.io",
        "freertos.org",
        "zephyrproject.org",
        "arm.com",
        "developer.arm.com",
    }
)

# Package registries: useful for "install X crate", noise for conceptual how-tos.
_PACKAGE_HOSTS = frozenset(
    {
        "crates.io",
        "pypi.org",
        "npmjs.com",
        "rubygems.org",
        "packagist.org",
        "hub.docker.com",
        "dockerhub.com",
        "proxy.golang.org",
    }
)

_NOISE_HOSTS = frozenset({"hub.docker.com", "dockerhub.com", "linkedin.com"})

_NON_WEB_STACK = re.compile(
    r"\b(kubernetes|k8s|helm|terraform|ansible|postgresql|postgres|mysql|sqlite|"
    r"rust|cargo|golang|goroutine|asyncio|fastapi|django|flask|pytorch|"
    r"java\.lang|nullpointerexception|cmake|llvm|ocaml|elixir|phoenix|"
    r"freertos|cortex|bare.?metal|opentelemetry|prometheus|grafana)\b",
    re.I,
)

_PACKAGE_INTENT = re.compile(
    r"\b(pip install|npm i|npm install|cargo add|crate|pypi|npm package|gem install|"
    r"library version|package version|dependency)\b",
    re.I,
)

_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "vs",
        "versus",
        "for",
        "with",
        "from",
        "into",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "is",
        "are",
        "be",
        "how",
        "what",
        "when",
        "why",
        "do",
        "does",
        "use",
        "using",
        "used",
        "docs",
        "documentation",
        "official",
        "guide",
        "tutorial",
        "example",
        "examples",
        "about",
        "into",
        "over",
        "under",
        "than",
        "then",
        "this",
        "that",
        "your",
        "my",
        "our",
        "explain",
        "overview",
        "describe",
        "introduction",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9_\.+#-]{2,}", re.I)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOP}


def _content_tokens(query: str) -> set[str]:
    """Drop ultra-short tokens that cause false topical matches (e.g. 'bi' in Power BI)."""
    return {t for t in _tokens(query) if len(t) >= 3 or t in {"go", "c++", "c#"}}


def is_doc_host(host: str) -> bool:
    if not host or host in _PACKAGE_HOSTS:
        return False
    if host in _DOC_HOST_EXACT:
        return True
    if host.startswith("docs.") or host.startswith("doc.") or host.startswith("developer."):
        return True
    return any(host == s or host.endswith("." + s) for s in _DOC_HOST_SUFFIXES)


def is_package_host(host: str) -> bool:
    return host in _PACKAGE_HOSTS or host.endswith(".crates.io")


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def rewrite_queries(query: str, mode: str) -> list[str]:
    """Return primary query plus optional alternates (general heuristics)."""
    q = " ".join(query.split())
    # Leading didactic words make engines return dictionaries, not CS docs.
    q = re.sub(r"^(explain|overview|describe|what is|what are)\s*:?\s*", "", q, flags=re.I)
    q = q.strip() or " ".join(query.split())
    out: list[str] = [q]
    if mode != "code":
        if mode == "academic" and "arxiv" not in q.lower() and len(q.split()) <= 6:
            out.append(f"{q} site:arxiv.org")
        return out

    lower = q.lower()
    if re.search(r"(error|exception|traceback|segfault|errno|failed to|cannot |can't )", lower):
        out.append(f"{q} site:stackoverflow.com")
        return _uniq(out)[:3]

    words = q.split()
    if len(words) <= 6 and not re.search(r"\bsite:", lower):
        out.append(f"{q} documentation")
        out.append(f"{q} official docs")
    elif len(words) >= 10 and not re.search(r"\b(how|vs|versus|compare)\b", lower):
        head = " ".join(words[:8])
        out.append(f"{head} documentation")

    # Ambiguous "embedded" without MCU context often retrieves analytics "embedded" pages.
    if re.search(r"\bembedded\b", lower) and re.search(
        r"\b(arm|cortex|mcu|rtos|freertos|bare.?metal|interrupt|firmware)\b", lower
    ):
        out.append(f"{q} microcontroller firmware")

    return _uniq(out)[:3]


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def engines_for_mode(mode: str, query: str, configured: str | None) -> str | None:
    if configured:
        engines = [e.strip() for e in configured.split(",") if e.strip()]
    elif mode == "code":
        engines = ["yep", "duckduckgo", "brave", "github", "stackoverflow"]
    else:
        return configured

    lower = query.lower()
    if mode == "code":
        # Drop package engines unless the user is clearly looking for a package.
        engines = [e for e in engines if e not in ("pypi", "npm", "crates.io") or _PACKAGE_INTENT.search(query)]
        if re.search(r"\b(css|html|dom|javascript|cors|http headers|accessibility|aria)\b", lower):
            if "mdn" not in engines:
                engines.append("mdn")
        if re.search(r"\b(docker|container image|dockerfile|compose)\b", lower):
            if "docker hub" not in engines:
                engines.append("docker hub")
        if _PACKAGE_INTENT.search(query) or re.search(r"\b(pip|pypi|crate|npm)\b", lower):
            for e in ("pypi", "github"):
                if e not in engines:
                    engines.append(e)
        # Always keep a CAPTCHA-resilient general engine first
        if "yep" not in engines:
            engines.insert(0, "yep")
    return ",".join(engines)


def lexical_overlap(query: str, hit: Hit) -> float:
    q_tokens = _content_tokens(query)
    if not q_tokens:
        return 0.0
    text_tokens = _tokens(f"{hit.title} {hit.snippet}")
    return len(q_tokens & text_tokens) / len(q_tokens)


def score_hit(hit: Hit, query: str, mode: str, *, semantic: float | None = None) -> float:
    host = _host(hit.url)
    overlap = lexical_overlap(query, hit)
    score = overlap * 4.0

    if semantic is not None:
        score += max(0.0, semantic) * 5.0

    if is_doc_host(host):
        score += 1.5
    if is_package_host(host):
        if _PACKAGE_INTENT.search(query):
            score += 1.0
        else:
            score -= 2.5

    if host.endswith("stackoverflow.com") or host.endswith("stackexchange.com"):
        score += 1.0 if mode == "code" else 0.3
    if "github.com" in host:
        score += 0.8 if mode == "code" else 0.2

    path = (urlparse(hit.url).path or "").lower()
    if any(p in path for p in ("/docs", "/doc/", "/documentation", "/reference", "/guide", "/specs")):
        score += 0.8
    if re.search(r"\b(documentation|reference|guide|tutorial|handbook|specification)\b", hit.title, re.I):
        score += 0.5

    if host in _NOISE_HOSTS and not re.search(r"\bdocker\b", query, re.I):
        score -= 3.0
    if host.endswith("developer.mozilla.org") and _NON_WEB_STACK.search(query):
        score -= 2.5
    if "power-bi" in (hit.url + hit.title).lower() and re.search(
        r"\b(arm|cortex|mcu|rtos|freertos|bare.?metal|firmware)\b", query, re.I
    ):
        score -= 4.0
    if host.endswith("learn.microsoft.com") and overlap < 0.15 and (semantic or 0) < 0.35:
        score -= 1.5

    if overlap < 0.08 and (semantic is None or semantic < 0.28):
        score -= 3.0

    return score


def rerank(
    hits: list[Hit],
    query: str,
    mode: str,
    limit: int,
    *,
    semantics: list[float] | None = None,
    min_overlap: float = 0.0,
    min_semantic: float = 0.0,
) -> list[Hit]:
    if not hits:
        return []
    if semantics is not None and len(semantics) != len(hits):
        raise ValueError("semantics length must match hits")

    scored: list[tuple[int, Hit, float, float, float | None]] = []
    for i, hit in enumerate(hits):
        sem = semantics[i] if semantics is not None else None
        ov = lexical_overlap(query, hit)
        if min_overlap and ov < min_overlap and (sem is None or sem < min_semantic):
            continue
        scored.append((i, hit, score_hit(hit, query, mode, semantic=sem), ov, sem))

    if not scored:
        scored = [
            (i, hit, score_hit(hit, query, mode, semantic=semantics[i] if semantics else None), 0.0, None)
            for i, hit in enumerate(hits)
        ]

    scored.sort(key=lambda row: (-row[2], row[0]))

    picked: list[Hit] = []
    host_counts: dict[str, int] = {}
    deferred: list[Hit] = []
    for _, hit, _, _, _ in scored:
        h = _host(hit.url)
        if host_counts.get(h, 0) >= 2:
            deferred.append(hit)
            continue
        host_counts[h] = host_counts.get(h, 0) + 1
        picked.append(hit)
        if len(picked) >= limit:
            break
    for hit in deferred:
        if len(picked) >= limit:
            break
        picked.append(hit)
    return picked[:limit]


def hit_text_for_embed(hit: Hit) -> str:
    return f"{hit.title}\n{hit.snippet}\n{hit.url}"
