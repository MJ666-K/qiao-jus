#!/usr/bin/env bash
# Register knowledge-service MCP server with OpenClaw.
# Usage: ./scripts/openclaw_setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example and fill in real values first."
  exit 1
fi

# Pull required env vars from .env
get_env() {
  grep -E "^$1=" .env | tail -1 | cut -d'=' -f2-
}

LLM_API_KEY=$(get_env LLM_API_KEY)
DATABASE_URL=$(get_env DATABASE_URL)
NEO4J_URI=$(get_env NEO4J_URI)
NEO4J_USER=$(get_env NEO4J_USER)
NEO4J_PASSWORD=$(get_env NEO4J_PASSWORD)
REDIS_URL=$(get_env REDIS_URL)
CELERY_BROKER_URL=$(get_env CELERY_BROKER_URL)
CELERY_RESULT_BACKEND=$(get_env CELERY_RESULT_BACKEND)
JWT_SECRET_KEY=$(get_env JWT_SECRET_KEY)

if ! command -v openclaw >/dev/null 2>&1; then
  echo "ERROR: openclaw CLI not installed."
  echo "Install from https://github.com/openclaw/openclaw"
  exit 1
fi

# Idempotent: drop existing registration if any
openclaw mcp unset knowledge 2>/dev/null || true

echo "Registering knowledge MCP server with OpenClaw..."
openclaw mcp add knowledge \
  --command python \
  --arg -m \
  --arg adapters.mcp_server \
  --cwd "$(pwd)" \
  --env LLM_API_KEY="$LLM_API_KEY" \
  --env DATABASE_URL="$DATABASE_URL" \
  --env NEO4J_URI="$NEO4J_URI" \
  --env NEO4J_USER="$NEO4J_USER" \
  --env NEO4J_PASSWORD="$NEO4J_PASSWORD" \
  --env REDIS_URL="$REDIS_URL" \
  --env CELERY_BROKER_URL="$CELERY_BROKER_URL" \
  --env CELERY_RESULT_BACKEND="$CELERY_RESULT_BACKEND" \
  --env JWT_SECRET_KEY="$JWT_SECRET_KEY"

echo
echo "Registered. Probing..."
if openclaw mcp doctor knowledge --probe 2>&1 | tee /tmp/ks_probe.log; then
  echo "✅ MCP server registered and reachable"
else
  echo "⚠️  Probe failed. See /tmp/ks_probe.log"
  echo "Common causes: slow litellm init (raise --connect-timeout), missing deps, wrong cwd."
fi

echo
echo "Tools exposed:"
openclaw mcp tools knowledge 2>/dev/null || true

echo
echo "Next: openclaw chat, then ask '查一下 NeuroScale N100 的算力'"
