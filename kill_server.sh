#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.gallery.env"

PORT="${GALLERY_PORT:-}"
if [[ -z "$PORT" && -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  PORT="${GALLERY_PORT:-}"
fi

# Prefer killing only this repo's server.py process.
PIDS="$(pgrep -f "$SCRIPT_DIR/server.py" || true)"

# Fallback to processes listening on configured port, if provided.
if [[ -z "$PIDS" && -n "$PORT" ]]; then
  PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
fi

if [[ -z "$PIDS" ]]; then
  echo "No running gallery server process found."
  exit 0
fi

echo "Stopping server process(es): $PIDS"
kill $PIDS || true

# Give processes a moment to stop gracefully, then force-kill leftovers.
sleep 1
REMAINING="$(echo "$PIDS" | xargs -n1 -I{} sh -c 'kill -0 {} 2>/dev/null && echo {}' || true)"
if [[ -n "$REMAINING" ]]; then
  echo "Force stopping remaining process(es): $REMAINING"
  kill -9 $REMAINING || true
fi

echo "Server stopped."
