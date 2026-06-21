# OpenClaw MCP 接入指南

本文档说明如何把 knowledge-service 暴露的 MCP tools 接入 OpenClaw Agent。

## 前置条件

- knowledge-service 已运行（`uvicorn api.main:app` 或 `docker compose up`）
- 在 knowledge-service 注册了一个账号，拿到 access_token（用于 MCP 工具调用的 `user_token` 参数）
- OpenClaw 已安装（`openclaw` CLI 可用）

## 暴露的 MCP Tools

knowledge-service 的 MCP server 通过 stdio 暴露 4 个工具：

| Tool | 用途 | 关键参数 |
|------|------|------|
| `knowledge_search` | Hybrid 向量检索（dense + BM25 + RRF + Reranker） | `query`, `top_k`, `dataset_id`, `user_token` |
| `graph_query` | 局部图谱遍历（实体 2-3 跳邻居 + 相关 chunks） | `query`, `depth`, `user_token` |
| `knowledge_answer` | 一站式 QA（检索 + 图谱增强 + LLM 答案） | `query`, `use_graph`, `user_token` |
| `knowledge_global_answer` | GraphRAG 全局 QA（跨文档宏观问题） | `query`, `user_token` |

**所有 tool 都需要 `user_token`** —— 这是 knowledge-service 的 JWT，用于多租户隔离。Agent 调用前必须先持有它。

## 配置方式（OpenClaw）

### 方式 1：CLI 注册（推荐）

```bash
openclaw mcp add knowledge \
  --command python \
  --arg -m \
  --arg adapters.mcp_server \
  --cwd /root/test/qiao-jus/knowledge-service \
  --env LLM_API_KEY=$LLM_API_KEY \
  --env DATABASE_URL=$DATABASE_URL \
  --env NEO4J_URI=$NEO4J_URI \
  --env NEO4J_USER=$NEO4J_USER \
  --env NEO4J_PASSWORD=$NEO4J_PASSWORD \
  --env REDIS_URL=$REDIS_URL \
  --env CELERY_BROKER_URL=$CELERY_BROKER_URL \
  --env CELERY_RESULT_BACKEND=$CELERY_RESULT_BACKEND \
  --env JWT_SECRET_KEY=$JWT_SECRET_KEY

# 验证连通
openclaw mcp doctor knowledge --probe
```

### 方式 2：JSON 配置

编辑 OpenClaw 的 `mcp.servers` 配置（位置因安装方式而异，参见 `openclaw mcp list`）：

```json
{
  "mcp": {
    "servers": {
      "knowledge": {
        "command": "python",
        "args": ["-m", "adapters.mcp_server"],
        "cwd": "/root/test/qiao-jus/knowledge-service",
        "env": {
          "LLM_API_KEY": "sk-...",
          "DATABASE_URL": "postgresql+asyncpg://ks:ks_secret@localhost:5432/knowledge",
          "NEO4J_URI": "bolt://localhost:7687",
          "NEO4J_USER": "neo4j",
          "NEO4J_PASSWORD": "neo4j_secret",
          "REDIS_URL": "redis://localhost:6379/0",
          "CELERY_BROKER_URL": "redis://localhost:6379/1",
          "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
          "JWT_SECRET_KEY": "<your-64-char-hex>"
        }
      }
    }
  }
}
```

注册后 OpenClaw Planner 会自动在合适场景下调用这些 tool。

## 让 Agent 拿到 user_token

Agent 需要在第一次调用时通过 `/auth/login` 拿到 access_token，作为后续 MCP tool 的 `user_token` 参数。两种模式：

### 模式 A：固定服务账号（推荐生产）

为 OpenClaw 单独注册一个服务账号（如 `openclaw@tenant.com`），把它的 token 预先注入 Agent 上下文（OpenClaw Memory 或环境变量）。

### 模式 B：动态登录

给 Agent 加一个登录辅助 tool（自定义 MCP），让它自己调 `/auth/login` 拿 token。

## 验证测试

```bash
# 1. 检查 MCP server 注册
openclaw mcp list
openclaw mcp status knowledge --verbose

# 2. 实际连接 + 列出工具
openclaw mcp probe knowledge --json

# 3. 在 Agent 会话里测试
openclaw chat
> "查一下 NeuroScale N100 的算力"
# Agent 应自动调用 knowledge_search 或 knowledge_answer
```

## 常见问题

### Q: `openclaw mcp doctor` 报 timeout
A: MCP server 首次启动要加载 litellm（5-10秒）。把 `--connect-timeout` 调到 15+。

### Q: tool 调用返回 "missing user token"
A: Agent 没传 `user_token` 参数。检查 prompt 让 Agent 知道必须传这个，或用模式 A 的固定 token 注入。

### Q: 图谱工具返回空
A: 文档还没处理完。检查 `GET /documents/{id}` 状态是 `done`，且 `GET /stats` 的 chunks > 0。`knowledge_global_answer` 需要先 `POST /graph/rebuild` 建社区。
