#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f ../deploy/docker-compose.yml up -d postgres qdrant neo4j redis

echo "==> Waiting for postgres..."
until docker exec fengqiao-postgres pg_isready -U fengqiao -d fengqiao >/dev/null 2>&1; do
  sleep 1
done

echo "==> Applying database migrations..."
.venv/bin/alembic upgrade head

pkill -f "uvicorn api.main:app" 2>/dev/null || true
pkill -f "celery.*pipeline.celery_app" 2>/dev/null || true

nohup .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/ks_api.log 2>&1 &
nohup .venv/bin/celery -A pipeline.celery_app worker -Q ingest,graph --concurrency=2 --loglevel=INFO > /tmp/ks_worker.log 2>&1 &

cat <<EOF

开发服务已启动:
  API:       http://localhost:8000/docs
  前端:      cd ../frontend && npm run dev → http://localhost:5173
  日志:
    API:     tail -f /tmp/ks_api.log
    Worker:  tail -f /tmp/ks_worker.log
  停止:      ./scripts/stop.sh

EOF
