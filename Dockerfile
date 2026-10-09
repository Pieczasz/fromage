FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md modes.json ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV FROMAGE_SEARXNG_URL=http://searxng:8080 \
    OLLAMA_HOST=http://ollama:11434 \
    FROMAGE_MEMORY=sqlite \
    FROMAGE_SQLITE_PATH=/data/memory.db \
    FROMAGE_PAGE_CACHE=/data/pages.db \
    FROMAGE_EMBED_MODEL=nomic-embed-text \
    FROMAGE_IMPROVE=1 \
    FROMAGE_SEMANTIC_RERANK=1 \
    FROMAGE_MODES_PATH=/app/modes.json \
    MCP_TRANSPORT=streamable-http \
    MCP_PORT=8765 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8765

CMD ["python", "-m", "fromage.mcp_server"]
