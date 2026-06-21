#!/bin/bash
set -e

# 枫桥智诉 · 一键打包脚本
# 用法: ./build.sh [--skip-frontend]

SKIP_FRONTEND=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DEPLOY_DIR="$PROJECT_ROOT/deploy"
DIST_DIR="$PROJECT_ROOT/deploy/dist"

echo "========================================"
echo "枫桥智诉 · 打包构建"
echo "========================================"

mkdir -p "$DIST_DIR"

# 1. 构建前端
if [ "$SKIP_FRONTEND" = false ]; then
    echo ""
    echo "[1/3] 构建前端..."
    cd "$PROJECT_ROOT/frontend"

    if [ ! -d "node_modules" ]; then
        echo "  安装前端依赖..."
        npm install
    fi

    npm run build

    # 复制构建产物
    rm -rf "$DIST_DIR/frontend"
    cp -r "$PROJECT_ROOT/frontend/dist" "$DIST_DIR/frontend"

    echo "  前端构建完成 → $DIST_DIR/frontend"
else
    echo ""
    echo "[1/3] 跳过前端构建 (--skip-frontend)"
fi

# 2. 打包后端
echo ""
echo "[2/3] 打包后端..."
cd "$PROJECT_ROOT/knowledge-service"

# 复制必要文件
rm -rf "$DIST_DIR/knowledge-service"
mkdir -p "$DIST_DIR/knowledge-service"

# 核心代码
cp -r src "$DIST_DIR/knowledge-service/"
cp pyproject.toml "$DIST_DIR/knowledge-service/"
cp Dockerfile "$DIST_DIR/knowledge-service/"
cp docker-compose.yml "$DIST_DIR/knowledge-service/"
cp .env.example "$DIST_DIR/knowledge-service/.env.template"
cp -r scripts "$DIST_DIR/knowledge-service/"

# 复制测试数据（可选）
if [ -d "docs/data" ]; then
    cp -r docs/data "$DIST_DIR/knowledge-service/"
fi

echo "  后端打包完成 → $DIST_DIR/knowledge-service"

# 3. 打包部署配置
echo ""
echo "[3/3] 打包部署配置..."
cp -r "$DEPLOY_DIR/nginx" "$DIST_DIR/"
cp "$DEPLOY_DIR/docker-compose.yml" "$DIST_DIR/"

echo "  部署配置打包完成 → $DIST_DIR/docker-compose.yml"

# 4. 创建发布包
echo ""
echo "[4/4] 生成发布包..."
cd "$DIST_DIR"
tar -czf "$PROJECT_ROOT/fengqiao-deploy-$(date +%Y%m%d-%H%M%S).tar.gz" .

echo ""
echo "========================================"
echo "打包完成！"
echo "========================================"
echo ""
echo "发布包位置: $PROJECT_ROOT/fengqiao-deploy-*.tar.gz"
echo ""
echo "解压后部署:"
echo "  tar -xzf fengqiao-deploy-*.tar.gz"
echo "  cd deploy"
echo "  cp knowledge-service/.env.template knowledge-service/.env"
echo "  # 编辑 knowledge-service/.env 填入必要配置"
echo "  docker compose up -d"
echo ""
