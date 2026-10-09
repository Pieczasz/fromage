FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md modes.json ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV OPEN_SEARCH_SEARXNG_URL=http://searxng:8080 \
    OLLAMA_HOST=http://ollama:11434 \
    OPEN_SEARCH_MEMORY=sqlite \
    OPEN_SEARCH_SQLITE_PATH=/data/memory.db \
    OPEN_SEARCH_PAGE_CACHE=/data/pages.db \
    OPEN_SEARCH_EMBED_MODEL=nomic-embed-text \
    OPEN_SEARCH_IMPROVE=1 \
    OPEN_SEARCH_SEMANTIC_RERANK=1 \
    OPEN_SEARCH_MODES_PATH=/app/modes.json \
    MCP_TRANSPORT=streamable-http \
    MCP_PORT=8765 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8765

CMD ["python", "-m", "open_search.mcp_server"]
