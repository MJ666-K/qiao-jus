#!/usr/bin/env bash
# Stop API + Worker (does NOT stop docker deps — use `docker compose down` for that).
set -euo pipefail
cd "$(dirname "$0")/.."

PID_DIR="$PWD/.run"
API_PID="$PID_DIR/api.pid"
WORKER_PID="$PID_DIR/worker.pid"

c_ok()   { printf "\033[32m✔ %s\033[0m\n" "$1"; }
c_info() { printf "\033[36m→ %s\033[0m\n" "$1"; }

# API
if [ -f "$API_PID" ]; then
  PID=$(cat "$API_PID" 2>/dev/null || echo "")
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    c_info "Stopping API (pid $PID)..."
    kill "$PID" 2>/dev/null || true
    for i in 1 2 3 4 5; do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
    kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
    c_ok "API stopped"
  fi
  rm -f "$API_PID"
fi

# Worker — also reap any orphan celery child processes
pkill -f "celery.*pipeline.celery_app" 2>/dev/null && c_ok "Worker stopped" || true
[ -f "$WORKER_PID" ] && rm -f "$WORKER_PID"

echo
c_ok "All app processes stopped"
c_info "Docker deps (postgres/qdrant/neo4j/redis) still running. To stop them:"
echo "  docker compose down"
