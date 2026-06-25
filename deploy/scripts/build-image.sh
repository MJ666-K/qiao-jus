#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
IMAGE="${FENGQIAO_API_IMAGE:-fengqiao-api:latest}"

docker build -t "$IMAGE" "$PROJECT_ROOT/knowledge-service"

echo "✓ $IMAGE 构建完成"
