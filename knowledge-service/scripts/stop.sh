#!/usr/bin/env bash
set -euo pipefail

pkill -f "uvicorn api.main:app" 2>/dev/null || true
pkill -f "celery.*pipeline.celery_app" 2>/dev/null || true

echo "API + Worker 已停止"
echo "停止 docker 依赖: docker compose -f ../deploy/docker-compose.yml down"
