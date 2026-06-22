#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

docker build -t fengqiao-api:latest "$PROJECT_ROOT/knowledge-service"

echo "✓ fengqiao-api:latest 构建完成"
echo "  部署: cd deploy && ./scripts/deploy.sh"
