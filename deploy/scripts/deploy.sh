#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
cd "$DEPLOY_DIR"

ENV_FILE="$PROJECT_ROOT/knowledge-service/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "⚠️  knowledge-service/.env 不存在，请先创建:"
    echo "   cp knowledge-service/.env.example knowledge-service/.env"
    echo "   编辑填入 LLM_API_KEY 和 JWT_SECRET_KEY"
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/frontend/dist" ]; then
    echo "构建前端..."
    cd "$PROJECT_ROOT/frontend"
    [ -d node_modules ] || npm install
    npm run build
    cd "$DEPLOY_DIR"
fi

docker compose up -d --build

cat <<EOF

部署完成:
  前端:   http://localhost
  API:    http://localhost:8000/docs
  Neo4j:  http://localhost:7474
  Qdrant: http://localhost:6333/dashboard
  数据:   $DEPLOY_DIR/data/
  停止:   docker compose down
  日志:   docker compose logs -f

EOF
