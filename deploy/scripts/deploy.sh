#!/usr/bin/env bash
# 一键部署：构建前端 → deploy/app/，构建后端镜像，docker compose up
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
DATA_DIR="$DEPLOY_DIR/data"
APP_DIR="$DEPLOY_DIR/app"

usage() {
    cat <<'EOF'
用法: ./scripts/deploy.sh [选项]

  (无选项)    构建前端 + 后端镜像，并启动全部容器
  --up-only   跳过构建，仅 docker compose up -d
  --help      显示此帮助

目录:
  deploy/data/   数据库持久化（postgres / qdrant / neo4j / redis）
  deploy/app/    前端静态文件（nginx 根目录）
  deploy/.env    容器环境变量（Docker 内网服务名）
EOF
}

build_frontend() {
    echo ">>> 构建前端 → deploy/app/"
    cd "$PROJECT_ROOT/frontend"
    [ -d node_modules ] || npm install
    npm run build
    mkdir -p "$APP_DIR"
    rm -rf "$APP_DIR"/*
    cp -a dist/. "$APP_DIR/"
    chmod -R a+rX "$APP_DIR"
    cd "$DEPLOY_DIR"
}

require_frontend() {
    if [ ! -f "$APP_DIR/index.html" ]; then
        echo "⚠️  deploy/app/index.html 不存在，访问站点会返回 403"
        echo "   请先构建前端: ./scripts/deploy.sh"
        exit 1
    fi
}

main() {
    local up_only=0
    for arg in "$@"; do
        case "$arg" in
            --up-only) up_only=1 ;;
            -h|--help) usage; exit 0 ;;
            *) echo "未知选项: $arg"; usage; exit 1 ;;
        esac
    done

    cd "$DEPLOY_DIR"

    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        echo "⚠️  deploy/.env 不存在:"
        echo "   cp deploy/.env.example deploy/.env"
        echo "   编辑填入 LLM_API_KEY、JWT_SECRET_KEY、OSS 等"
        exit 1
    fi

    mkdir -p \
        "$DATA_DIR/postgres" \
        "$DATA_DIR/qdrant" \
        "$DATA_DIR/neo4j" \
        "$DATA_DIR/redis" \
        "$APP_DIR"

    if [ "$up_only" -eq 1 ]; then
        require_frontend
        echo ">>> 启动容器..."
        docker compose up -d
    else
        build_frontend
        echo ">>> 构建后端镜像..."
        "$SCRIPT_DIR/build-image.sh"
        echo ">>> 启动容器..."
        docker compose up -d
    fi

    cat <<EOF

部署完成:
  前端:   http://localhost
  API:    http://localhost/api/docs
  数据:   $DATA_DIR/
  静态:   $APP_DIR/
  停止:   docker compose down
  日志:   docker compose logs -f
EOF
}

main "$@"
