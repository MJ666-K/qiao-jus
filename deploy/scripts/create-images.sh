#!/bin/bash
set -e

# 枫桥智诉 · 构建 Docker 镜像
# 用法: ./create-images.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "========================================"
echo "枫桥智诉 · 构建 Docker 镜像"
echo "========================================"

# 1. 构建后端镜像
echo ""
echo "[1/2] 构建后端镜像..."
cd "$PROJECT_ROOT/knowledge-service"

docker build -t fengqiao-api:latest \
    --build-arg PYTHON_VERSION=3.12 \
    -f Dockerfile \
    "$PROJECT_ROOT/knowledge-service"

echo "  镜像构建完成: fengqiao-api:latest"

# 2. 构建前端镜像
echo ""
echo "[2/2] 构建前端镜像..."
cd "$PROJECT_ROOT/frontend"

docker build -t fengqiao-frontend:latest \
    -f Dockerfile \
    "$PROJECT_ROOT/frontend" 2>/dev/null || {
    # 如果前端没有 Dockerfile，使用 nginx
    echo "  前端使用 nginx 镜像打包"
    docker build -t fengqiao-frontend:latest \
        -f - \
        "$PROJECT_ROOT/frontend" << 'NGINX_DOCKERFILE'
FROM nginx:alpine
COPY dist /usr/share/nginx/html
COPY ../deploy/nginx/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
NGINX_DOCKERFILE
}

echo "  镜像构建完成: fengqiao-frontend:latest"

echo ""
echo "========================================"
echo "镜像构建完成！"
echo "========================================"
echo ""
echo "本地镜像:"
docker images | grep fengqiao
echo ""
echo "下一步:"
echo "  1. 标记镜像版本: docker tag fengqiao-api:latest your-registry/fengqiao-api:v1.0.0"
echo "  2. 推送镜像: docker push your-registry/fengqiao-api:v1.0.0"
echo ""
