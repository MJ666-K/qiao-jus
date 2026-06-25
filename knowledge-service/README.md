# Knowledge Service

RAG + 知识图谱底座，通过 REST API 暴露能力，支持模块化 Skill 架构。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                knowledge-service                      │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  FastAPI    │  │  Celery     │  │  Skills   │ │
│  │  REST API   │  │  异步流水线  │  │  模块化   │ │
│  └──────┬──────┘  └──────┬─────┘  └─────┬─────┘ │
│         │                │               │        │
│  ┌──────┴────────────────┴───────────────┴─────┐ │
│  │        PostgreSQL │ Qdrant │ Neo4j            │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

特性：
- 父子切分 RAG（检索小块，返回完整上下文）
- Hybrid 检索：OpenAI-compatible Embedding（默认 DashScope `text-embedding-v3`，1024 维 dense）+ BM25 (sparse) + Reciprocal Rank Fusion
- GraphRAG 基础：LLM 抽取实体/关系，Neo4j 存储，Local Search 图谱遍历
- Provider 无关：通过 LiteLLM 接入任何 OpenAI-compatible 端点（DashScope/ZhipuAI/OpenAI/vLLM 等）
- JWT 鉴权 + 多租户隔离（tenant_id 贯穿三库）
- Celery 异步流水线（parse → chunk+embed → graph_build）

## 快速开始

### 一键启动（推荐）

```bash
cd knowledge-service

# 1. 首次：复制环境变量模板并填入 LLM API key
cp .env.example .env
# 编辑 .env：必填 LLM_API_KEY、JWT_SECRET_KEY（生成：openssl rand -hex 32）

# 2. 首次：建虚拟环境并装依赖
uv venv --python 3.12 .venv
uv pip install -e .

# 3. 启动！（docker 依赖 + API + Worker 一并起）
./scripts/start.sh
```

`start.sh` 做了什么：
- 启动 docker 依赖（postgres / qdrant / neo4j / redis）并等就绪
- 用 venv 启动 FastAPI（:8000）和 Celery Worker
- 健康检查通过后才返回成功
- 幂等：已运行的会重启

启动成功后：
| 入口 | 地址 |
|---|---|
| **Web UI** | http://localhost:5173 （Vue 前端，见 `../frontend`） |
| API 文档（Swagger） | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| Qdrant 控制台 | http://localhost:6333/dashboard |
| Neo4j Browser | http://localhost:7474 （bolt://localhost:7687） |

### 常用命令

```bash
./scripts/start.sh     # 启动 docker 依赖 + API + Worker
./scripts/stop.sh      # 停止 API + Worker（保留 docker 依赖）

# 完全停止包括 docker 依赖：
docker compose -f ../deploy/docker-compose.yml down
```

### 日志位置

```
API:     /tmp/ks_api.log
Worker:  /tmp/ks_worker.log
```

### 首次使用流程

1. 启动后端 `./scripts/start.sh`，前端 `cd ../frontend && npm run dev`
2. 浏览器打开 http://localhost:5173 → 注册账号（自动建租户）
2. 左侧切到"数据集" → 新建一个
3. 切到"文档" → 选择刚建的数据集 → 拖拽 .md / .pdf / .docx 上传
4. 等 status 变成 `done`（侧栏会刷新）
5. 用"检索"或"问答"测试
6. 进阶：在"图谱"页点"重建社区"，再试"全局问答"（GraphRAG 跨文档综合）

## 项目结构

```
knowledge-service/
├── src/             Python 源码（src layout）
│   ├── api/         FastAPI 路由 + deps
│   ├── core/        config / security / tenant / llm
│   ├── models/      SQLAlchemy 2.0
│   ├── schemas/     Pydantic v2
│   ├── storage/     postgres / qdrant / neo4j 适配
│   ├── ingest/      parser (unstructured) / chunker (parent-child)
│   ├── pipeline/    Celery + tasks (parse/chunk+embed/graph_build)
│   ├── retrieve/    hybrid (dense+BM25+RRF) / reranker
│   └── adapters/    mcp_server
├── scripts/         start/stop/init_db
├── tests/           smoke test
└── .env             配置（cp .env.example .env）
```

前端 UI 已迁移至项目根目录 [`frontend/`](../frontend)，由 Vue SPA 独立部署。

## 测试

```bash
# 单元 smoke
pytest -q tests/

# 端到端（有完整打印输出，推荐）
./scripts/e2e_smoke_test.py

# 导入 docs/data 测试数据
./scripts/seed_platform_data.py
```

E2E 通过标准：健康检查、登录、检索命中、问答有内容。浏览器测试账号：`seed@demo.com` / `seed12345`。

## 开发

```bash
# 本地开发（需要先启 postgres/qdrant/neo4j/redis）
pip install -e .[dev]
pytest -q

# 类型/格式检查
ruff check .
mypy src/core src/api
```

## 下一步扩展

| 方向 | 怎么做 |
|------|------|
| 启用 Reranker | 默认 DashScope `qwen3-rerank`（`src/retrieve/reranker.py`） |
| 全局图谱问答 | 实现 GraphRAG 社区检测 + 层次摘要（level 0..N） |
| 权限细粒度 | 在 Qdrant payload 加 `acl_read`，Qdrant 过滤 |
| 文档版本控制 | 给 `documents` 加 `version` 字段，重新上传走 reindex |
| 增量图谱更新 | 监听 document.delete 事件，级联清理 Entity orphan |
