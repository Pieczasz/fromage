from fromage.models import Hit
from fromage.rank import (
    engines_for_mode,
    lexical_overlap,
    rewrite_queries,
    rerank,
    score_hit,
)


def test_rewrite_code_short_adds_docs_hint():
    qs = rewrite_queries("React useEffect hook", "code")
    assert qs[0] == "React useEffect hook"
    assert any("documentation" in q for q in qs)


def test_rewrite_error_adds_stackoverflow():
    qs = rewrite_queries("TypeError: cannot read property map", "code")
    assert any("stackoverflow.com" in q for q in qs)


def test_engines_skip_mdn_for_k8s():
    eng = engines_for_mode("code", "kubernetes liveness probe", "duckduckgo,github")
    assert "mdn" not in eng.split(",")


def test_engines_add_mdn_for_css():
    eng = engines_for_mode("code", "css flexbox gap", "duckduckgo")
    assert "mdn" in eng.split(",")


def test_rerank_prefers_docs_over_dockerhub():
    hits = [
        Hit("img", "https://hub.docker.com/r/foo/bar", "container image"),
        Hit("Docs", "https://docs.python.org/3/library/asyncio.html", "asyncio tasks"),
        Hit("SO", "https://stackoverflow.com/q/1", "asyncio cancel task"),
    ]
    ranked = rerank(hits, "python asyncio cancel task", "code", limit=3)
    urls = [h.url for h in ranked]
    assert "hub.docker.com" in urls[-1]
    assert any("docs.python.org" in u or "stackoverflow.com" in u for u in urls[:2])
    assert score_hit(hits[1], "python asyncio cancel task", "code") > score_hit(
        hits[0], "python asyncio cancel task", "code"
    )


def test_rerank_demotes_mdn_for_non_web_stack():
    hits = [
        Hit("MDN", "https://developer.mozilla.org/en-US/docs/Web/API/XRLightProbe", "probe"),
        Hit(
            "K8s",
            "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
            "livenessProbe readinessProbe",
        ),
    ]
    ranked = rerank(
        hits,
        "Kubernetes livenessProbe vs readinessProbe for Go HTTP",
        "code",
        limit=2,
    )
    assert "kubernetes.io" in ranked[0].url


def test_demote_package_registry_for_conceptual_query():
    hits = [
        Hit("crate", "https://crates.io/crates/prometheus-scraper", "scraper"),
        Hit("docs", "https://prometheus.io/docs/practices/histograms/", "histogram vs summary"),
    ]
    ranked = rerank(hits, "Prometheus histogram vs summary when to use", "code", limit=2)
    assert "prometheus.io" in ranked[0].url


def test_demote_powerbi_embedded_for_mcu_query():
    hits = [
        Hit(
            "Power BI",
            "https://learn.microsoft.com/en-us/rest/api/power-bi/",
            "Power BI REST APIs for embedded analytics",
        ),
        Hit(
            "ARM",
            "https://developer.arm.com/documentation/dui0552/a/the-cortex-m3-processor/exception-model/vector-table",
            "Cortex-M3 interrupt vector table bare metal",
        ),
    ]
    q = "embedded ARM Cortex-M bare metal interrupt vector table"
    assert score_hit(hits[1], q, "code") > score_hit(hits[0], q, "code")
    ranked = rerank(hits, q, "code", limit=2)
    assert "arm.com" in ranked[0].url or "developer.arm.com" in ranked[0].url


def test_semantic_boost_outranks_weak_lexical():
    hits = [
        Hit("unrelated", "https://example.com/a", "gardening tips for tomatoes"),
        Hit("otel", "https://opentelemetry.io/docs/", "distributed tracing metrics logs"),
    ]
    # Without semantics, gardening may lose; with strong semantic on otel, it wins
    ranked = rerank(
        hits,
        "observability OpenTelemetry tracing",
        "code",
        limit=2,
        semantics=[0.1, 0.75],
    )
    assert "opentelemetry.io" in ranked[0].url


def test_lexical_overlap_ignores_stopwords():
    hit = Hit("x", "https://example.com", "the and for with")
    assert lexical_overlap("the and for with observability", hit) == 0.0
