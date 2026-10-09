# fromage

Web search, page reading, and a small memory for your coding agent. Self-hosted, no API keys, no accounts.

**SearXNG** finds links, **read** turns a page into clean markdown, **remember/recall** keeps a tiny vector memory on disk. One `docker compose up`, exposed over MCP to Claude Code, Cursor, Codex, OpenCode, and anything else that speaks MCP.

```bash
git clone https://github.com/Pieczasz/fromage && cd fromage
docker compose up -d --build
claude mcp add --transport http fromage http://127.0.0.1:8765/mcp   # or see below for other agents
```

Then ask your agent: *"search for OpenTelemetry histogram vs summary and read the best result"*.

MCP endpoint: **http://127.0.0.1:8765/mcp**. Search UI: http://127.0.0.1:8888. Everything binds to `127.0.0.1` only.

## Tools

| Tool | What it does |
|------|--------------|
| `search(query, mode="general", limit=8)` | Metasearch via SearXNG, then reranks. Modes: `general`, `academic`, `code`, `news`. |
| `read(url, max_chars=20000, start=0)` | Fetches a page and returns its main content as markdown, code blocks included. Long pages come back in slices (`next_start`). Cached for 24h. |
| `remember(url)` | Fetches, chunks, and embeds a page into local memory. |
| `recall(query, k=5)` | Returns the stored chunks closest to the query. |

Errors come back as readable messages (for example `unknown mode 'x'; known: academic, code, general, news`), so the agent can correct itself.

## Connect your agent

| App | What to do |
|-----|------------|
| **Claude Code** | `claude mcp add --transport http fromage http://127.0.0.1:8765/mcp` |
| **Cursor** | `./scripts/connect.sh cursor` writes `.cursor/mcp.json` |
| **OpenCode** | merge [`clients/opencode.json`](clients/opencode.json) into your OpenCode config |
| **Codex** | paste [`clients/codex.toml`](clients/codex.toml) into `~/.codex/config.toml` |
| **Claude Desktop** | `./scripts/connect.sh claude` and merge into Claude's MCP config (stdio via Docker) |

## What's in the box

| Service | Port | Job |
|---------|------|-----|
| `mcp` | 8765 | The four tools above (Streamable HTTP) |
| `searxng` | 8888 | Metasearch over Google, Bing, DuckDuckGo, Brave, Wikipedia, GitHub, Stack Overflow, arXiv and more |
| `ollama` | internal | Embeddings (`nomic-embed-text`, pulled on first boot) |
| `qdrant` | 6333 | Optional vector DB: `docker compose --profile vector up -d`, then set `FROMAGE_MEMORY=qdrant` and `FROMAGE_QDRANT_URL=http://qdrant:6333` |

Memory defaults to a SQLite file in the `mcp_data` volume.

## What "private" means here

No account, no API key, and no single provider holding your search history. Your queries do still reach the upstream engines (Google, Bing, and so on) through SearXNG, from your IP. If that matters, run it behind a VPN or point SearXNG at a proxy.

`read` refuses URLs that resolve to private, loopback, or link-local addresses (checked on every redirect), caps responses at 5 MB and 30 s, so a prompt-injected page cannot make your agent poke at your LAN or the other containers.

## Configuration

Set these under `environment:` on the `mcp` service in `compose.yaml`. Defaults are in the [`Dockerfile`](Dockerfile).

| Variable | Default | Meaning |
|----------|---------|---------|
| `FROMAGE_IMPROVE` | `1` | Query rewriting and reranking. `0` returns raw SearXNG order. |
| `FROMAGE_SEMANTIC_RERANK` | `1` | Use embeddings in reranking (needs Ollama). |
| `FROMAGE_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model. |
| `FROMAGE_MEMORY` | `sqlite` | `sqlite` or `qdrant`. |
| `FROMAGE_MODES_PATH` | unset | JSON file to add or override search modes (`{"mode": {"categories": "...", "engines": "a,b"}}`). |
| `OLLAMA_HOST` | `http://ollama:11434` | Point at another Ollama. |

**On a Mac**, Ollama inside Docker has no GPU, so `remember` is slow (a minute or more for a long page) and semantic reranking adds a few seconds per search. Native Ollama is about 15x faster: run it on the host, `ollama pull nomic-embed-text`, and set `OLLAMA_HOST=http://host.docker.internal:11434` on the `mcp` service.

## Limits

Public engines rate-limit scrapers. A normal agent session is fine, but hundreds of searches in a few minutes from one IP will get Google, DuckDuckGo, and Brave to block you for a while (SearXNG then reports them as `access denied` or `too many requests`, and results thin out). Each improved search sends up to three queries upstream; set `FROMAGE_IMPROVE=0` to send one.

## Benchmark

[`bench/web_cs.jsonl`](bench/web_cs.jsonl) has 1,000 generated queries across 16 topics, split 90/10 into train and test by query family, so paraphrases never cross the split. A case counts as a hit when a result from one of the topic's reference sites (for example `prometheus.io` for observability) lands in the top 5.

```bash
fromage-bench --web-only --web bench/web_cs.jsonl --split test --delay 3   # fromage
FROMAGE_IMPROVE=0 fromage-bench --web-only --web bench/web_cs.jsonl --split test --delay 3   # raw SearXNG
```

Keep the delay high, or see Limits above.

## Similar projects

fromage is deliberately small: about 1,700 lines of Python, MIT licensed, one compose file. If it is not what you need, these are good:

- [wigolo](https://github.com/KnockOutEZ/wigolo): far more features (crawl, research, browser fetching). Node, AGPL.
- [mcp-searxng](https://github.com/ihor-sokoliuk/mcp-searxng): search and read only, for an existing SearXNG instance.
- [web-search-mcp](https://github.com/mrkrsl/web-search-mcp): search via real browsers, no SearXNG.
- [Cloudflare Web Search API](https://developers.cloudflare.com/web-search/): hosted, paid per request, own indexes.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

MIT licensed. PRs welcome.
