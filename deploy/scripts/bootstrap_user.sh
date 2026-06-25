#!/usr/bin/env bash
# 在生产库中创建首个管理员（不经 HTTP 注册/验证码）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
cd "$DEPLOY_DIR"

EMAIL="${1:-seed@demo.com}"
PASSWORD="${2:-seed12345}"
ROLE="${3:-admin}"

if [ "${#PASSWORD}" -lt 8 ]; then
    echo "ERROR: 密码至少 8 位（当前 ${#PASSWORD} 位）"
    exit 1
fi

docker compose exec api python -m scripts.create_user \
    --email "$EMAIL" \
    --password "$PASSWORD" \
    --role "$ROLE"

cat <<EOF

可用以下账号登录前端（需填写验证码）:
  邮箱: $EMAIL
  密码: $PASSWORD

EOF
