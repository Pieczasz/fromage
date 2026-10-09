# fromage

Your agents can search the web. Locally. Without shipping your queries to a random cloud provider.

**SearXNG** finds links, **read** pulls the page, **remember/recall** keeps a tiny brain on disk. One Docker Compose. MCP for Cursor, Claude, Codex, and OpenCode.

```
docker compose up -d --build
./scripts/connect.sh
```

Then ask your agent: *“search for OpenTelemetry histogram vs summary”*.

All ports bind to `127.0.0.1` only; nothing is reachable from your network.

MCP endpoint: **http://127.0.0.1:8765/mcp**  
Search UI (optional): http://127.0.0.1:8888

---

## Plug into your coding agent

After `docker compose up -d --build`:

| App                | What to do                                                                          |
|--------------------|-------------------------------------------------------------------------------------|
| **Cursor**         | `./scripts/connect.sh cursor` writes `.cursor/mcp.json`                             |
| **OpenCode**       | merge [`clients/opencode.json`](clients/opencode.json) into your OpenCode config    |
| **Codex**          | paste [`clients/codex.toml`](clients/codex.toml) into `~/.codex/config.toml`        |
| **Claude Desktop** | `./scripts/connect.sh claude` and merge into Claude’s MCP config (stdio via Docker) |

```bash
./scripts/connect.sh          # cheat sheet
./scripts/connect.sh all      # write Cursor config + print the rest
```

Tools you get: `search`, `read`, `remember`, `recall`.

---

## What’s in the box

| Service   | Port  | Job                                                   |
|-----------|-------|-------------------------------------------------------|
| `mcp`     | 8765  | Agent tools (Streamable HTTP)                         |
| `searxng` | 8888  | Metasearch                                            |
| `ollama`  | none  | Embeddings (`nomic-embed-text`, pulled on first boot) |

Optional vector DB:

```bash
docker compose --profile vector up -d
```

Then set `FROMAGE_MEMORY=qdrant` / `FROMAGE_QDRANT_URL=http://qdrant:6333` on the `mcp` service.

---

## Play with it yourself

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Modes live in [`modes.json`](modes.json). Ranking/search knobs are env vars on the `mcp` service (`FROMAGE_IMPROVE`, `FROMAGE_SEMANTIC_RERANK`, …).

Benchmarks (optional): `fromage-bench --web-only --web bench/web_cs.jsonl --split test`

---

MIT licensed. PRs welcome
