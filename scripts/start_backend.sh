#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
APP_DIR="$ROOT_DIR/backend"
APP_IMPORT="app.main:app"

START_PORT="${1:-8000}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: Python virtual environment not found at $PYTHON_BIN"
  echo "Create it first: python3 -m venv .venv && ./.venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

port_in_use() {
  local port="$1"
  lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1
}

PORT="$START_PORT"
while port_in_use "$PORT"; do
  PORT=$((PORT + 1))
done

if [[ "$PORT" != "$START_PORT" ]]; then
  echo "Port $START_PORT is busy. Using $PORT instead."
fi

echo "Starting backend on http://127.0.0.1:$PORT"
exec "$PYTHON_BIN" -m uvicorn "$APP_IMPORT" --reload --app-dir "$APP_DIR" --port "$PORT"
