#!/usr/bin/env python3
"""Generate a large multi-topic web bench with a frozen 90/10 split.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

SEED = "open-search-web-v2"
OUT = Path("bench/web_cs.jsonl")
META = Path("bench/web_cs_meta.json")

# topic: (mode, host families, distinctive terms, query templates)
# Hosts are broad families, not single-page overfitting targets.
TOPICS: dict[str, dict] = {
    "observability": {
        "mode": "code",
        "hosts": ["opentelemetry.io", "prometheus.io", "grafana.com", "jaegertracing.io", "datadoghq.com", "honeycomb.io"],
        "terms": ["opentelemetry", "prometheus", "tracing", "metrics", "observability", "histogram", "span"],
        "queries": [
            "OpenTelemetry tracing spans metrics logs",
            "Prometheus histogram vs summary when to use",
            "Grafana dashboard Prometheus datasource",
            "Jaeger distributed tracing architecture",
            "OpenTelemetry collector exporters configuration",
            "RED method monitoring microservices",
            "Prometheus alerting rules best practices",
            "OpenTelemetry auto instrumentation Java",
            "service level objectives SLI SLO error budget",
            "structured logging vs metrics vs traces",
            "Datadog APM vs OpenTelemetry vendor neutral",
            "exemplars linking Prometheus metrics to traces",
            "cardinality explosion Prometheus labels",
            "OpenTelemetry context propagation W3C traceparent",
            "Grafana Loki log aggregation with Prometheus",
            "observability pipeline sampling head based vs tail based",
            "Prometheus remote write Thanos long term storage",
            "eBPF observability Cilium Hubble",
            "OpenTelemetry semantic conventions HTTP spans",
            "profiling continuous profiling Parca Pyroscope",
        ],
    },
    "embedded": {
        "mode": "code",
        "hosts": ["developer.arm.com", "freertos.org", "zephyrproject.org", "nordicsemi.com", "st.com", "arduino.cc"],
        "terms": ["cortex", "freertos", "interrupt", "firmware", "bare metal", "gpio", "dma", "rtos"],
        "queries": [
            "ARM Cortex-M interrupt vector table bare metal",
            "FreeRTOS priority inversion mutex priority inheritance",
            "Zephyr RTOS device tree overlay GPIO",
            "STM32 HAL vs LL drivers DMA transfer",
            "embedded C volatile keyword memory mapped registers",
            "Nordic nRF52 SoftDevice BLE stack",
            "Watchdog timer embedded firmware design",
            "I2C vs SPI vs UART embedded peripherals",
            "CMSIS DSP library Cortex-M floating point",
            "bootloader UART firmware update MCU",
            "hard fault handler ARM Cortex-M debugging",
            "RTOS task stack size FreeRTOS uxTaskGetStackHighWaterMark",
            "bare metal vs RTOS when to choose",
            "DMA circular buffer ADC sampling embedded",
            "MPU memory protection unit Cortex-M",
            "Arduino AVR interrupt service routine",
            "linker script sections .text .data .bss embedded",
            "power management sleep modes STM32",
            "CAN bus embedded automotive message filtering",
            "JTAG SWD debugging probe OpenOCD",
        ],
    },
    "python": {
        "mode": "code",
        "hosts": ["docs.python.org", "realpython.com", "pypi.org", "peps.python.org"],
        "terms": ["python", "asyncio", "gil", "pytest", "typing", "dataclass", "pip"],
        "queries": [
            "Python asyncio TaskGroup CancelledError 3.11",
            "Python GIL explained multithreading vs multiprocessing",
            "pytest fixtures parametrize conftest",
            "dataclasses field default_factory mutable",
            "typing Protocol vs ABC Python",
            "pep 8 style guide indentation",
            "venv vs poetry vs uv Python packaging",
            "contextvars asyncio request context",
            "CPython vs PyPy performance differences",
            "memoryview buffer protocol numpy",
            "functools lru_cache when not to use",
            "match case structural pattern matching Python",
            "importlib reload module caveats",
            "slot classes __slots__ memory",
            "walrus operator assignment expression",
            "pathlib vs os.path modern Python",
            "fastapi Depends injection tutorial",
            "django ORM select_related prefetch_related",
            "sqlalchemy 2.0 async session",
            "mypy strict mode gradual typing",
        ],
    },
    "javascript": {
        "mode": "code",
        "hosts": ["developer.mozilla.org", "nodejs.org", "react.dev", "tc39.es", "typescriptlang.org"],
        "terms": ["javascript", "typescript", "promise", "react", "node", "async", "module"],
        "queries": [
            "JavaScript event loop microtasks macrotasks",
            "TypeScript discriminated unions exhaustiveness",
            "React useEffect cleanup dependency array",
            "Node.js worker threads vs cluster",
            "ES modules vs CommonJS interoperability",
            "Promise allSettled vs Promise all",
            "fetch AbortController cancel request",
            "Next.js App Router server components",
            "Vite vs webpack bundler differences",
            "Zod schema validation TypeScript",
            "weakmap vs map memory leaks",
            "structuredClone vs JSON parse stringify",
            "TC39 temporal proposal date time",
            "React Query vs SWR data fetching",
            "Node.js streams backpressure",
            "CORS preflight Access-Control-Allow-Origin",
            "service workers caching strategies",
            "WebAssembly and JavaScript interop",
            "eslint flat config typescript",
            "pnpm vs npm workspace monorepo",
        ],
    },
    "systems": {
        "mode": "code",
        "hosts": ["kernel.org", "man7.org", "docs.kernel.org", "lwn.net", "freebsd.org"],
        "terms": ["linux", "kernel", "syscall", "epoll", "cgroup", "namespace", "mmap"],
        "queries": [
            "Linux epoll edge triggered vs level triggered",
            "cgroups v2 cpu memory controller",
            "Linux namespaces pid network mount",
            "mmap anonymous vs file backed pages",
            "page cache writeback dirty pages",
            "futex wait wake userspace locking",
            "io_uring vs epoll performance",
            "BPF CO-RE libbpf tutorials",
            "OOM killer score Linux",
            "transparent huge pages THP tradeoffs",
            "seccomp BPF sandboxing",
            "splice tee zero copy pipes",
            "NUMA memory policy Linux",
            "CFS scheduler Completely Fair Scheduler",
            "inode dentry VFS Linux",
            "systemd unit dependencies After Requires",
            "strace vs perf vs bpftrace",
            "copy on write fork memory",
            "TCP congestion control BBR vs cubic",
            "udev rules device naming",
        ],
    },
    "distributed": {
        "mode": "code",
        "hosts": ["apache.org", "kubernetes.io", "etcd.io", "raft.github.io", "martin.kleppmann.com"],
        "terms": ["consensus", "raft", "paxos", "kafka", "sharding", "replication", "cap"],
        "queries": [
            "Raft consensus leader election log replication",
            "Paxos vs Raft explained",
            "CAP theorem PACELC consistency latency",
            "Kafka consumer group rebalance",
            "exactly once semantics distributed systems",
            "etcd watch API Kubernetes",
            "consistent hashing virtual nodes",
            "quorum read write N W R",
            "two phase commit vs saga pattern",
            "vector clocks vs Lamport timestamps",
            "CRDT conflict free replicated data types",
            "Kubernetes etcd backup restore",
            "partition tolerance network split brain",
            "idempotent message processing retries",
            "ZooKeeper ZAB protocol",
            "gRPC streaming bidirectional",
            "service mesh Istio sidecar",
            "distributed lock Redis Redlock critique",
            "change data capture Debezium",
            "outbox pattern transactional messaging",
        ],
    },
    "databases": {
        "mode": "code",
        "hosts": ["postgresql.org", "mongodb.com", "redis.io", "mysql.com", "sqlite.org", "use-the-index-luke.com"],
        "terms": ["sql", "index", "transaction", "isolation", "query", "postgres", "replication"],
        "queries": [
            "PostgreSQL EXPLAIN ANALYZE nested loop hash join",
            "SQL isolation levels phantom read",
            "B-tree vs hash index when to use",
            "Redis persistence RDB AOF tradeoffs",
            "MongoDB aggregation pipeline stages",
            "SQLite WAL mode concurrency",
            "covering index include columns",
            "MVCC PostgreSQL vacuum freeze",
            "connection pooling PgBouncer",
            "N+1 query problem ORM",
            "window functions ROW_NUMBER partition",
            "foreign key cascade delete",
            "database sharding strategies",
            "MySQL InnoDB vs MyISAM",
            "JSON columns PostgreSQL jsonb indexing",
            "prepared statements SQL injection",
            "read replicas lag consistency",
            "materialized views refresh concurrently",
            "deadlock detection databases",
            "OLTP vs OLAP column stores",
        ],
    },
    "networking": {
        "mode": "code",
        "hosts": ["ietf.org", "cloudflare.com", "nginx.org", "wireshark.org", "rfc-editor.org"],
        "terms": ["tcp", "tls", "http", "dns", "quic", "cdn", "latency"],
        "queries": [
            "TCP slow start congestion window",
            "TLS 1.3 handshake 0-RTT",
            "HTTP/2 multiplexing head of line blocking",
            "QUIC UDP HTTP/3 overview",
            "DNS over HTTPS vs DNS over TLS",
            "CDN cache key design Cloudflare",
            "Nginx reverse proxy WebSocket upgrade",
            "MTU path discovery black hole",
            "BGP anycast routing CDN",
            "NAT hole punching STUN TURN",
            "Wireshark TCP retransmission analysis",
            "TLS certificate chain validation",
            "HTTP caching Cache-Control ETag",
            "gRPC vs REST latency overhead",
            "load balancer L4 vs L7",
            "IPv6 neighbor discovery",
            "SYN flood mitigation SYN cookies",
            "Keep-Alive connection pooling",
            "mTLS service to service auth",
            "packet loss vs latency application impact",
        ],
    },
    "security": {
        "mode": "code",
        "hosts": ["owasp.org", "cve.mitre.org", "nvd.nist.gov", "portswigger.net", "letsencrypt.org"],
        "terms": ["oauth", "xss", "csrf", "vulnerability", "encryption", "jwt", "tls"],
        "queries": [
            "OWASP Top 10 injection XSS CSRF",
            "OAuth 2.0 authorization code PKCE",
            "JWT common vulnerabilities none algorithm",
            "SQL injection parameterized queries",
            "SSRF cloud metadata 169.254.169.254",
            "password hashing argon2 bcrypt",
            "SameSite cookie CSRF defense",
            "Content Security Policy XSS mitigation",
            "certificate transparency logs",
            "dependency supply chain attacks npm",
            "secrets management vault rotation",
            "threat modeling STRIDE",
            "buffer overflow stack canaries",
            "CORS misconfiguration credentials",
            "mTLS mutual TLS microservices",
            "CVE scoring CVSS explained",
            "Let's Encrypt ACME DNS challenge",
            "webauthn passkeys phishing resistant",
            "side channel timing attacks crypto",
            "RBAC vs ABAC authorization",
        ],
    },
    "ml": {
        "mode": "academic",
        "hosts": ["arxiv.org", "pytorch.org", "tensorflow.org", "huggingface.co", "scikit-learn.org"],
        "terms": ["transformer", "gradient", "embedding", "training", "neural", "attention", "loss"],
        "queries": [
            "Attention Is All You Need transformer paper",
            "backpropagation chain rule neural networks",
            "cross entropy loss softmax",
            "batch normalization vs layer normalization",
            "Adam optimizer bias correction",
            "dropout regularization explained",
            "BERT masked language modeling",
            "RAG retrieval augmented generation",
            "embedding cosine similarity semantic search",
            "diffusion models DDPM overview",
            "gradient vanishing exploding LSTM",
            "transfer learning fine tuning LLM",
            "evaluation metrics BLEU ROUGE F1",
            "overfitting early stopping regularization",
            "contrastive learning SimCLR",
            "mixture of experts MoE transformers",
            "quantization INT8 inference",
            "RLHF reinforcement learning from human feedback",
            "feature stores for ML pipelines",
            "data leakage train test contamination",
        ],
    },
    "compilers": {
        "mode": "code",
        "hosts": ["llvm.org", "gcc.gnu.org", "rust-lang.org", "craftinginterpreters.com"],
        "terms": ["compiler", "llvm", "ir", "parser", "codegen", "optimization", "ssa"],
        "queries": [
            "LLVM IR SSA form basics",
            "recursive descent vs LR parsing",
            "register allocation graph coloring",
            "constant folding dead code elimination",
            "CRAFTING interpreters bytecode VM",
            "GCC vs Clang optimization flags",
            "Rust MIR borrow check pipeline",
            "ahead of time vs JIT compilation",
            "link time optimization LTO",
            "abstract syntax tree visitor pattern",
            "type inference Hindley Milner",
            "escape analysis heap to stack",
            "WebAssembly compilation targets",
            "inline caching JavaScript engines",
            "control flow graph basic blocks",
            "peephole optimization assembly",
            "symbol tables scopes name resolution",
            "garbage collection mark sweep generational",
            "FFI foreign function interface ABI",
            "debug info DWARF line tables",
        ],
    },
    "algorithms": {
        "mode": "academic",
        "hosts": ["wikipedia.org", "geeksforgeeks.org", "cp-algorithms.com", "arxiv.org"],
        "terms": ["complexity", "graph", "dynamic programming", "sort", "hash", "tree", "algorithm"],
        "queries": [
            "Dijkstra vs A-star pathfinding",
            "Big O time complexity amortized analysis",
            "union find disjoint set path compression",
            "dynamic programming knapsack",
            "red black tree rotations",
            "bloom filter false positive rate",
            "consistent hashing load balancing",
            "suffix array string matching",
            "max flow min cut Ford Fulkerson",
            "quicksort vs mergesort average case",
            "B+ tree database indexes",
            "skip lists probabilistic structures",
            "topological sort DAG",
            "segment trees range queries",
            "approximation algorithms NP hard",
            "randomized algorithms Monte Carlo Las Vegas",
            "hash collision resolution chaining open addressing",
            "minimum spanning tree Kruskal Prim",
            "dynamic programming memoization recursion",
            "cache oblivious algorithms",
        ],
    },
    "cloud_devops": {
        "mode": "code",
        "hosts": ["kubernetes.io", "docs.docker.com", "terraform.io", "aws.amazon.com", "helm.sh"],
        "terms": ["kubernetes", "docker", "terraform", "ci", "deployment", "helm", "pipeline"],
        "queries": [
            "Kubernetes liveness vs readiness probes",
            "Docker multi stage build alpine",
            "Terraform state locking S3 DynamoDB",
            "Helm chart values override image tag",
            "GitHub Actions OIDC AWS roles",
            "Kubernetes HorizontalPodAutoscaler",
            "Infrastructure as Code drift detection",
            "blue green vs canary deployments",
            "Docker layer caching CI",
            "kubectl rollout undo deployment",
            "Argo CD GitOps continuous delivery",
            "Prometheus operator Kubernetes",
            "Terraform modules versioning",
            "pod security standards restricted",
            "service mesh vs ingress controller",
            "secrets as files vs env vars k8s",
            "CI pipeline test flake quarantine",
            "cost allocation Kubernetes labels",
            "ephemeral containers debugging pods",
            "Pulumi vs Terraform comparison",
        ],
    },
    "graphics": {
        "mode": "code",
        "hosts": ["khronos.org", "opengl.org", "developer.nvidia.com", "learnopengl.com", "vulkan.org"],
        "terms": ["shader", "vulkan", "opengl", "gpu", "raster", "mesh", "texture"],
        "queries": [
            "Vulkan graphics pipeline barriers",
            "OpenGL vs Vulkan abstraction level",
            "PBR physically based rendering Cook Torrance",
            "GPU GLSL fragment shader basics",
            "deferred shading vs forward rendering",
            "mesh shaders NVIDIA Turing",
            "texture mipmapping anisotropic filtering",
            "ray tracing BVH acceleration",
            "compute shaders GPGPU",
            "sRGB gamma correction rendering",
            "depth buffer z-fighting",
            "instanced rendering draw calls",
            "SPIR-V intermediate representation",
            "WebGPU vs WebGL differences",
            "normal mapping tangent space",
            "GPU memory coalescing",
            "frame graph render passes",
            "signed distance fields fonts",
            "occlusion culling hierarchical Z",
            "color spaces ACES tone mapping",
        ],
    },
    "formal_methods": {
        "mode": "academic",
        "hosts": ["tlaplus", "coq.inria.fr", "lean-lang.org", "spinroot.com", "arxiv.org"],
        "terms": ["tla+", "proof", "model checking", "invariant", "formal", "verification", "theorem"],
        "queries": [
            "TLA+ PlusCal distributed algorithm verification",
            "model checking Spin Promela",
            "Coq proof assistant dependent types",
            "Lean 4 theorem proving mathlib",
            "temporal logic LTL CTL",
            "invariant safety liveness properties",
            "bounded model checking SAT",
            "refinement mapping TLA+",
            "Hoare logic preconditions postconditions",
            "symbolic execution KLEE",
            "Abstract interpretation static analysis",
            "Isabelle HOL interactive theorem proving",
            "Alloy analyzer relational modeling",
            "SMT solvers Z3 applications",
            "formal verification hardware Verilog",
            "weak memory models C11",
            "separation logic concurrent programs",
            "proof carrying code",
            "runtime verification monitoring",
            "certified compilers CompCert",
        ],
    },
    "hci_privacy": {
        "mode": "general",
        "hosts": ["w3.org", "eff.org", "gdpr.eu", "nist.gov", "acm.org"],
        "terms": ["privacy", "accessibility", "gdpr", "consent", "usability", "a11y", "tracking"],
        "queries": [
            "WCAG 2.2 accessibility contrast ratios",
            "GDPR lawful basis consent cookies",
            "differential privacy epsilon definition",
            "browser fingerprinting defenses",
            "usable security password managers",
            "ARIA roles screen readers",
            "privacy by design principles",
            "dark patterns dark patterns UX",
            "Do Not Track vs Global Privacy Control",
            "k-anonymity vs differential privacy",
            "informed consent HCI research ethics",
            "CAPTCHA accessibility issues",
            "end to end encryption messaging threat model",
            "P3P failed web privacy standard",
            "federated learning privacy",
            "cookie banners ePrivacy",
            "inclusive design cognitive load",
            "NIST privacy framework",
            "phishing susceptibility user studies",
            "anonymous credentials Tor onion services",
        ],
    },
}


def assign_split(case_id: str, train_ratio: float = 0.9) -> str:
    """Stable hash split, not random each run."""
    h = hashlib.sha256(f"{SEED}:{case_id}".encode()).hexdigest()
    # first 8 hex as int
    bucket = int(h[:8], 16) / 0xFFFFFFFF
    return "train" if bucket < train_ratio else "test"


def main() -> None:
    cases: list[dict] = []
    n = 0

    for topic, spec in TOPICS.items():
        mode = spec["mode"]
        hosts = spec["hosts"]
        terms = spec["terms"]
        for i, q in enumerate(spec["queries"]):
            cid = f"{topic}-{i:03d}"
            cases.append(
                {
                    "id": cid,
                    "query": q,
                    "mode": mode,
                    "topic": topic,
                    "url_substrings": hosts,
                    "snippet_terms": terms,
                    "tags": [topic, "generated"],
                    "difficulty": "medium" if i >= 10 else "easy",
                    "split": assign_split(cid),
                    "dup_of": None,
                }
            )
            n += 1

            # Paraphrase near-duplicate; avoid bare "Explain" (dictionary spam)
            para = f"{q} explained with examples" if "example" not in q.lower() else f"{q} deep dive"
            pid = f"{topic}-p{i:03d}"
            cases.append(
                {
                    "id": pid,
                    "query": para,
                    "mode": mode,
                    "topic": topic,
                    "url_substrings": hosts,
                    "snippet_terms": terms,
                    "tags": [topic, "generated", "paraphrase"],
                    "difficulty": "medium",
                    "split": assign_split(pid),
                    "dup_of": cid,
                }
            )
            n += 1

            # Exact duplicate query, different id; should get same topical outcome
            if i % 2 == 0:
                did = f"{topic}-d{i:03d}"
                cases.append(
                    {
                        "id": did,
                        "query": q,
                        "mode": mode,
                        "topic": topic,
                        "url_substrings": hosts,
                        "snippet_terms": terms,
                        "tags": [topic, "generated", "duplicate"],
                        "difficulty": "easy",
                        "split": assign_split(did),
                        "dup_of": cid,
                    }
                )
                n += 1

        # Cross-topic hard negatives: same language/tool words, different topic intent
        # (still labeled for the intended topic)
        if topic == "observability":
            hq = "Prometheus Go client library instrument HTTP handler histograms"
            hid = "observability-hard-go"
            cases.append(
                {
                    "id": hid,
                    "query": hq,
                    "mode": "code",
                    "topic": "observability",
                    "url_substrings": hosts,
                    "snippet_terms": terms + ["instrument", "client"],
                    "tags": [topic, "hard", "shared-lang"],
                    "difficulty": "hard",
                    "split": assign_split(hid),
                    "dup_of": None,
                }
            )
        if topic == "embedded":
            hq = "Go embedded systems TinyGo microcontroller GPIO"
            hid = "embedded-hard-go"
            cases.append(
                {
                    "id": hid,
                    "query": hq,
                    "mode": "code",
                    "topic": "embedded",
                    "url_substrings": hosts + ["tinygo.org"],
                    "snippet_terms": terms + ["tinygo", "microcontroller"],
                    "tags": [topic, "hard", "shared-lang"],
                    "difficulty": "hard",
                    "split": assign_split(hid),
                    "dup_of": None,
                }
            )
        if topic == "python":
            hq = "Python asyncio observability OpenTelemetry instrumentation"
            # intentional ambiguity: python + observability, labeled python-primary via hosts, dual terms
            hid = "python-hard-otel"
            cases.append(
                {
                    "id": hid,
                    "query": hq,
                    "mode": "code",
                    "topic": "python",
                    "url_substrings": ["docs.python.org", "opentelemetry.io", "pypi.org"],
                    "snippet_terms": ["asyncio", "opentelemetry", "python"],
                    "tags": [topic, "hard", "cross-topic"],
                    "difficulty": "hard",
                    "split": assign_split(hid),
                    "dup_of": None,
                }
            )

    # Pad to >= 1000 with templated variants if needed
    templates_extra = [
        ("best practices for {q}", "howto"),
        ("official documentation {q}", "docs"),
        ("{q} tutorial for beginners", "tutorial"),
        ("difference between concepts in {q}", "compare"),
    ]
    base_topics = list(TOPICS.items())
    extra_i = 0
    while len(cases) < 1000:
        topic, spec = base_topics[extra_i % len(base_topics)]
        q0 = spec["queries"][extra_i % len(spec["queries"])]
        tmpl, tag = templates_extra[extra_i % len(templates_extra)]
        q = tmpl.format(q=q0)
        cid = f"extra-{extra_i:04d}"
        cases.append(
            {
                "id": cid,
                "query": q,
                "mode": spec["mode"],
                "topic": topic,
                "url_substrings": spec["hosts"],
                "snippet_terms": spec["terms"],
                "tags": [topic, "generated", tag, "templated"],
                "difficulty": "medium",
                "split": assign_split(cid),
                "dup_of": None,
            }
        )
        extra_i += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    splits = Counter(c["split"] for c in cases)
    topics = Counter(c["topic"] for c in cases)
    meta = {
        "seed": SEED,
        "count": len(cases),
        "train": splits["train"],
        "test": splits["test"],
        "train_ratio": splits["train"] / len(cases),
        "topics": dict(topics),
        "note": "Frozen hash split on id. Tune only looking at train; report test blindly.",
    }
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
