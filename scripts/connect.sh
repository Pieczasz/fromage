#!/usr/bin/env bash
# Print / install MCP snippets for Cursor, Claude, Codex, OpenCode.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="$ROOT/compose.yaml"
URL="${OPEN_SEARCH_MCP_URL:-http://127.0.0.1:8765/mcp}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [print|cursor|claude|codex|opencode|all]

  print      show where to paste configs (default)
  cursor     write .cursor/mcp.json in this repo
  claude     merge hint for Claude Desktop config
  codex      print Codex toml snippet
  opencode   print OpenCode mcp block
  all        cursor + print others
EOF
}

print_all() {
  cat <<EOF
open-search MCP: $URL
(compose file: $COMPOSE)

1) Start the stack:
   docker compose -f "$COMPOSE" up -d --build

2) Wire your agent:

Cursor:   copy clients/cursor.mcp.json to .cursor/mcp.json (or run: $0 cursor)
OpenCode: merge clients/opencode.json into ~/.config/opencode/opencode.jsonc
Claude:   merge clients/claude_desktop.json into Claude Desktop config
          (replace COMPOSE_FILE with: $COMPOSE)
Codex:    paste clients/codex.toml into ~/.codex/config.toml

3) Reload MCP / restart the app. Ask: "search for OpenTelemetry tracing"
EOF
}

write_cursor() {
  mkdir -p "$ROOT/.cursor"
  if ! cat >"$ROOT/.cursor/mcp.json" <<EOF
{
  "mcpServers": {
    "open-search": {
      "url": "$URL"
    }
  }
}
EOF
  then
    echo "Could not write $ROOT/.cursor/mcp.json; copy clients/cursor.mcp.json manually."
    return 1
  fi
  echo "Wrote $ROOT/.cursor/mcp.json"
}

cmd="${1:-print}"
case "$cmd" in
  print) print_all ;;
  cursor) write_cursor ;;
  claude)
    sed "s|COMPOSE_FILE|$COMPOSE|g" "$ROOT/clients/claude_desktop.json"
    ;;
  codex)
    sed "s|COMPOSE_FILE|$COMPOSE|g" "$ROOT/clients/codex.toml"
    ;;
  opencode)
    cat "$ROOT/clients/opencode.json"
    ;;
  all)
    write_cursor
    print_all
    ;;
  -h|--help) usage ;;
  *) usage; exit 1 ;;
esac
