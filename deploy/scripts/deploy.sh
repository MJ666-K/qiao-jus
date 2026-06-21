#!/bin/bash
set -e

# 枫桥智诉 · 一键部署脚本
# 用法: ./deploy.sh [--stop] [--logs]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
cd "$DEPLOY_DIR"

show_help() {
    cat << EOF
枫桥智诉 · 部署脚本

用法: ./deploy.sh [选项]

选项:
    --stop     停止所有服务
    --logs     查看运行日志
    --restart  重启服务
    --status   查看服务状态
    --build    只构建不启动
    -h, --help 显示帮助

示例:
    ./deploy.sh              # 启动服务
    ./deploy.sh --stop       # 停止服务
    ./deploy.sh --logs       # 查看日志
    ./deploy.sh --restart    # 重启服务
EOF
}

stop_services() {
    echo "停止服务..."
    docker compose down
    echo "服务已停止"
}

start_services() {
    echo "启动服务..."
    docker compose up -d --build

    echo ""
    echo "等待服务启动..."
    sleep 5

    # 检查健康状态
    for i in {1..30}; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            echo ""
            echo "✓ 服务启动成功！"
            echo ""
            echo "访问地址:"
            echo "  前端界面: http://localhost"
            echo "  API 文档:  http://localhost:8000/docs"
            echo "  Neo4j:     http://localhost:7474"
            echo "  Qdrant:    http://localhost:6333/dashboard"
            return 0
        fi
        echo -n "."
        sleep 2
    done

    echo ""
    echo "✗ 服务启动超时，请检查日志: ./deploy.sh --logs"
    return 1
}

show_logs() {
    docker compose logs -f --tail=100
}

show_status() {
    echo ""
    echo "服务状态:"
    docker compose ps
    echo ""
    echo "健康检查:"
    curl -sf http://localhost:8000/health > /dev/null 2>&1 && echo "  API: ✓" || echo "  API: ✗"
    curl -sf http://localhost:6333/health > /dev/null 2>&1 && echo "  Qdrant: ✓" || echo "  Qdrant: ✗"
    curl -sf http://localhost:7474 > /dev/null 2>&1 && echo "  Neo4j: ✓" || echo "  Neo4j: ✗"
}

restart_services() {
    stop_services
    start_services
}

build_only() {
    echo "构建镜像..."
    docker compose build
    echo "构建完成"
}

# 主逻辑
case "${1:-}" in
    --stop)
        stop_services
        ;;
    --logs)
        show_logs
        ;;
    --restart)
        restart_services
        ;;
    --status)
        show_status
        ;;
    --build)
        build_only
        ;;
    -h|--help)
        show_help
        ;;
    "")
        start_services
        ;;
    *)
        echo "未知参数: $1"
        show_help
        exit 1
        ;;
esac
