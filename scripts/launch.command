#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  Expense Categorizer — One-click launcher
#  Double-click this file in Finder, or run: ./launch.command
# ─────────────────────────────────────────────────────────

# Change to the directory this script lives in so all
# relative paths resolve correctly even when run from Finder.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

ROOT_DIR="$(pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
APP_DIR="$ROOT_DIR/backend"
LOG_FILE="$ROOT_DIR/logs/backend_server.log"

# ── 1. Check virtual environment ──────────────────────────
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Virtual environment not found. Setting it up now…"
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r backend/requirements.txt
  echo "Dependencies installed."
fi

# ── 2. Find a free port starting at 8000 ─────────────────
port_in_use() { lsof -iTCP:"$1" -sTCP:LISTEN -n -P >/dev/null 2>&1; }
PORT=8000
while port_in_use "$PORT"; do
  echo "Port $PORT in use, trying $((PORT + 1))…"
  PORT=$((PORT + 1))
done

# ── 3. Start backend in the background ───────────────────
echo "Starting backend on http://127.0.0.1:$PORT …"
"$PYTHON_BIN" -m uvicorn app.main:app \
  --app-dir "$APP_DIR" \
  --port "$PORT" \
  --log-level warning \
  > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!

# ── 4. Wait until the server responds (up to 10 s) ───────
echo "Waiting for backend to be ready…"
READY=0
for i in {1..20}; do
  if curl -s "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 0.5
done

if [[ $READY -eq 0 ]]; then
  echo "Backend did not start in time. Check $LOG_FILE for details."
  exit 1
fi

echo "Backend ready (PID $BACKEND_PID). Logs → $LOG_FILE"

# ── 5. Patch UI to use the detected port ─────────────────
# The UI auto-detects ports 8000/8001/8002 — no patching needed.

# ── 6. Open the UI in the default browser ────────────────
echo "Opening UI…"
open "http://127.0.0.1:$PORT/"

echo ""
echo "────────────────────────────────────────────────────"
echo "  Expense Categorizer is running."
echo "  Backend : http://127.0.0.1:$PORT"
echo "  API docs: http://127.0.0.1:$PORT/docs"
echo ""
echo "  Press Ctrl+C here to stop the backend server."
echo "────────────────────────────────────────────────────"

# ── 7. Keep script alive so Ctrl+C stops the backend ─────
trap "echo 'Shutting down backend…'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID
