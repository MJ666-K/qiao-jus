#!/usr/bin/env bash
# Show current status of all services.
set -euo pipefail
cd "$(dirname "$0")/.."

c_ok()   { printf "\033[32m✔ %s\033[0m\n" "$1"; }
c_err()  { printf "\033[31m✖ %s\033[0m\n" "$1"; }
c_dim()  { printf "\033[2m  %s\033[0m\n" "$1"; }

PID_DIR="$PWD/.run"
API_PID="$PID_DIR/api.pid"
WORKER_PID="$PID_DIR/worker.pid"

echo "=== knowledge-service 状态 ==="
echo

# Docker deps
echo "[Docker 依赖]"
for svc in postgres qdrant neo4j redis; do
  status=$(docker compose ps "$svc" --format json 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        s = d.get('Status','') or d.get('State','')
        print(s)
    except: pass
" 2>/dev/null | head -1)
  if [ -n "$status" ]; then c_ok "$svc: $status"; else c_err "$svc: not running"; fi
done
echo

# API
echo "[API]"
if [ -f "$API_PID" ] && kill -0 "$(cat "$API_PID" 2>/dev/null)" 2>/dev/null; then
  PID=$(cat "$API_PID")
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    H=$(curl -s http://localhost:8000/health)
    c_ok "API running (pid $PID) — $H"
  else
    c_err "API process alive (pid $PID) but healthcheck failed"
  fi
else
  c_err "API not running"
fi
c_dim "log: tail -f /tmp/ks_api.log"
echo

# Worker
echo "[Worker]"
if pgrep -f "celery.*pipeline.celery_app" >/dev/null 2>&1; then
  c_ok "Worker running ($(pgrep -f 'celery.*pipeline.celery_app' | wc -l) processes)"
else
  c_err "Worker not running"
fi
c_dim "log: tail -f /tmp/ks_worker.log"
echo

echo "[端口]"
for port in 8000:API 5432:Postgres 6333:Qdrant 7474:Neo4j-http 7687:Neo4j-bolt 6379:Redis; do
  p=${port%%:*}; name=${port##*:}
  if ss -ltn 2>/dev/null | grep -q ":$p "; then c_ok "$name :$p"; else c_err "$name :$p"; fi
done
