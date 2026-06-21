#!/usr/bin/env bash
# One-shot start: docker deps + venv API + venv Celery worker.
# Usage: ./scripts/start.sh [--logs]
#   --logs  after start, tail all logs (Ctrl-C to detach, services keep running)
set -euo pipefail
cd "$(dirname "$0")/.."

PID_DIR="$PWD/.run"
LOG_DIR="/tmp"
API_PID="$PID_DIR/api.pid"
WORKER_PID="$PID_DIR/worker.pid"
mkdir -p "$PID_DIR"

c_ok()   { printf "\033[32m✔ %s\033[0m\n" "$1"; }
c_wait() { printf "\033[33m⏳ %s\033[0m\n" "$1"; }
c_err()  { printf "\033[31m✖ %s\033[0m\n" "$1"; }
c_info() { printf "\033[36m→ %s\033[0m\n" "$1"; }

# ---------- 1. Pre-flight ----------
[ -f .env ] || { c_err ".env not found. Run: cp .env.example .env && edit"; exit 1; }
[ -d .venv ] || { c_err ".venv not found. Run: uv venv --python 3.12 .venv && uv pip install -e ."; exit 1; }
command -v docker >/dev/null || { c_err "docker not installed"; exit 1; }

# ---------- 2. Docker deps ----------
c_wait "Starting docker deps (postgres / qdrant / neo4j / redis)..."
docker compose up -d postgres qdrant neo4j redis >/dev/null 2>&1
c_ok "Docker deps started"

c_wait "Waiting for postgres healthcheck..."
for i in {1..30}; do
  if docker compose ps postgres | grep -q "healthy"; then c_ok "postgres ready"; break; fi
  [ "$i" = "30" ] && { c_err "postgres not healthy after 30s"; exit 1; }
  sleep 1
done

# ---------- 3. Stop stale API/Worker if any ----------
if [ -f "$API_PID" ] && kill -0 "$(cat "$API_PID")" 2>/dev/null; then
  c_info "API already running (pid $(cat "$API_PID")), restarting..."
  kill "$(cat "$API_PID")" 2>/dev/null || true
  sleep 1
fi
if [ -f "$WORKER_PID" ] && kill -0 "$(cat "$WORKER_PID")" 2>/dev/null; then
  c_info "Worker already running (pid $(cat "$WORKER_PID")), restarting..."
  kill "$(cat "$WORKER_PID")" 2>/dev/null || true
  pkill -9 -f "celery.*pipeline.celery_app" 2>/dev/null || true
  sleep 2
fi

# ---------- 4. Start API ----------
c_wait "Starting FastAPI..."
nohup setsid .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 \
  > "$LOG_DIR/ks_api.log" 2>&1 < /dev/null &
echo $! > "$API_PID"
disown 2>/dev/null || true

c_wait "Waiting for API healthcheck..."
for i in {1..30}; do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then c_ok "API ready"; break; fi
  [ "$i" = "30" ] && { c_err "API not ready. Tail of log:"; tail -20 "$LOG_DIR/ks_api.log"; exit 1; }
  sleep 1
done

# ---------- 5. Start Worker ----------
c_wait "Starting Celery worker..."
nohup setsid .venv/bin/celery -A pipeline.celery_app worker \
  -Q ingest,graph --concurrency=2 --loglevel=INFO -n "ks@%h" \
  > "$LOG_DIR/ks_worker.log" 2>&1 < /dev/null &
echo $! > "$WORKER_PID"
disown 2>/dev/null || true

c_wait "Waiting for worker ready..."
for i in {1..60}; do
  # "ready" 是最终标志；但 mingle 慢时可能延迟出现，也接受 "Connected" 作为早期信号
  if grep -q -E "ready\.|mingle: all alone" "$LOG_DIR/ks_worker.log" 2>/dev/null; then c_ok "Worker ready"; break; fi
  [ "$i" = "60" ] && { c_err "Worker not ready. Tail of log:"; tail -20 "$LOG_DIR/ks_worker.log"; exit 1; }
  sleep 1
done

# ---------- 6. Done ----------
cat <<EOF

$(c_ok "All services up")

  Web UI:     http://localhost:8000
  API docs:   http://localhost:8000/docs
  Health:     http://localhost:8000/health
  Qdrant UI:  http://localhost:6333/dashboard
  Neo4j:      http://localhost:7474  (bolt://localhost:7687)

  Logs:
    API:     tail -f $LOG_DIR/ks_api.log
    Worker:  tail -f $LOG_DIR/ks_worker.log

  Stop:      ./scripts/stop.sh
  Status:    ./scripts/status.sh

EOF

if [ "${1:-}" = "--logs" ]; then
  c_info "Tailing logs (Ctrl-C to detach; services keep running)..."
  tail -f "$LOG_DIR/ks_api.log" "$LOG_DIR/ks_worker.log" || true
fi
