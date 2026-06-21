# 枫桥智诉 · Fengqiao Intelligent Legal Assistant

法律智能辅助平台，提供合同审查、纠纷研判、证据指引等法律服务。

## 项目组成

```
枫桥智诉
├── frontend/           Vue 3 前端应用
└── knowledge-service/  Python 后端服务（RAG + 知识图谱）
```

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                            │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    knowledge-service                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  FastAPI    │  │  Celery     │  │  Skills            │ │
│  │  REST API   │  │  异步流水线  │  │  模块化技能        │ │
│  └──────┬──────┘  └──────┬─────┘  └──────────┬──────────┘ │
│         │                │                    │            │
│  ┌──────┴────────────────┴────────────────────┴────────┐ │
│  │                   存储层                              │ │
│  │  PostgreSQL (元数据)  │  Qdrant (向量)  │  Neo4j (图谱) │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

### 前端 (frontend/)

| 技术 | 用途 |
|------|------|
| Vue 3 + Composition API | 框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Element Plus | UI 组件库 |
| D3.js | 知识图谱可视化 |
| Pinia | 状态管理 |
| Axios | HTTP 客户端 |

### 后端 (knowledge-service/)

| 技术 | 用途 |
|------|------|
| Python 3.12 | 运行时 |
| FastAPI | REST API 框架 |
| Pydantic v2 | 数据验证 |
| SQLAlchemy 2.0 | ORM |
| Celery | 异步任务队列 |
| Redis | 消息队列 / 缓存 |

### 存储

| 技术 | 用途 |
|------|------|
| PostgreSQL | 业务数据、元数据 |
| Qdrant | 向量数据库（Embedding 存储与检索） |
| Neo4j | 知识图谱（实体关系存储） |

### AI 能力

| 技术 | 用途 |
|------|------|
| LiteLLM | LLM 统一网关（支持 DashScope/ZhipuAI/OpenAI/vLLM） |
| DashScope Embedding | 向量化（text-embedding-v3, 1024 维） |
| Hybrid Search | BM25 + Dense Vector + RRF 融合检索 |

## 功能模块

| 页面 | 路由 | 功能说明 |
|------|------|----------|
| 概览 | `/dashboard` | 管理员数据统计 |
| 知识库 | `/datasets` | 平台公共库管理（法规/类案） |
| 文档 | `/documents` | 上传 → 切分 → 向量 → 图谱 |
| 检索 | `/search` | Hybrid RAG 检索 |
| 图谱 | `/graph` | 实体可视化 + 社区检测 |
| 问答 | `/chat` | 局部 RAG + GraphRAG 问答 |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Docker 和 Docker Compose

### 1. 启动后端服务

```bash
cd knowledge-service

# 首次：复制环境变量模板
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY、JWT_SECRET_KEY

# 安装依赖
uv venv --python 3.12 .venv
uv pip install -e .

# 一键启动（docker 依赖 + API + Worker）
./scripts/start.sh
```

启动成功后访问：
- Web UI: http://localhost:5173
- API 文档: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 业务流程

### 文档处理流水线

```
上传文档 (PDF/MD/DOCX)
    │
    ▼
解析 ──► 切分 (父子切分)
    │
    ▼
向量化 (Embedding)
    │
    ├──► Qdrant (向量索引)
    │
    ▼
图谱构建 (LLM 抽取实体/关系)
    │
    ▼
Neo4j (知识图谱)
```

### 问答流程

```
用户提问
    │
    ▼
意图识别
    │
    ├──► 通用问答 ──► 平台法规 + 类案 + 图谱
    │
    └──► 报告问答 ──► 用户报告 + 用户材料 + 平台库
              │
              ▼
         Hybrid 检索
         (Dense + BM25 + RRF)
              │
              ▼
         LLM 生成 + 引用
```

## 项目结构

### 前端结构

```
frontend/
├── src/
│   ├── api/          API 客户端
│   ├── components/    公共组件
│   ├── views/         页面组件
│   ├── stores/        Pinia 状态
│   ├── router/        路由配置
│   └── types/         TypeScript 类型
└── dist/              构建产物
```

### 后端结构

```
knowledge-service/
├── src/
│   ├── api/          FastAPI 路由
│   ├── core/         配置/安全/租户/LLM
│   ├── models/       SQLAlchemy 模型
│   ├── schemas/      Pydantic schema
│   ├── storage/      存储适配器
│   ├── ingest/       文档解析/切分
│   ├── pipeline/     Celery 任务
│   ├── retrieve/     检索模块
│   └── adapters/     MCP Server
├── scripts/           启动脚本
└── tests/            测试
```

## 数据模型

### 核心实体

- **Document**: 文档元数据（类型、状态、OSS 路径）
- **DocumentChunk**: 文本块 + 向量 + 元数据
- **GraphNode**: 图谱节点（实体）
- **GraphEdge**: 图谱边（关系）
- **Community**: 社区（实体聚类）

### 文档类型

| 类型 | 说明 | 存储位置 |
|------|------|----------|
| `law` | 法律法规 | 平台公共库 |
| `case` | 裁判案例 | 平台公共库 |
| `compliance` | 合规条款 | 平台公共库 |
| `contract` | 合同 | 用户私有库 |
| `dispute` | 纠纷描述 | 用户私有库 |

## 环境变量

### knowledge-service

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | 是 | 大模型 API Key |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥 |
| `DATABASE_URL` | 否 | PostgreSQL 连接串 |
| `QDRANT_URL` | 否 | Qdrant 地址 |
| `NEO4J_URL` | 否 | Neo4j 连接串 |

### frontend

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VITE_API_BASE` | `/api` | API 前缀 |

## 一键打包部署

项目提供了完整的打包部署脚本，位于 `deploy/` 目录。

### 目录结构

```
deploy/
├── docker-compose.yml     # Docker 编排配置
├── scripts/
│   ├── build.sh          # 一键打包脚本
│   ├── deploy.sh         # 一键部署脚本
│   └── create-images.sh  # 构建 Docker 镜像
└── nginx/
    └── nginx.conf        # Nginx 配置
```

### 快速部署

```bash
# 1. 一键打包（生成部署包）
cd deploy/scripts
./build.sh

# 2. 上传到服务器并解压
tar -xzf ../../fengqiao-deploy-*.tar.gz
cd deploy

# 3. 编辑配置
vim knowledge-service/.env
# 填入必要配置:
#   LLM_API_KEY=your-api-key
#   JWT_SECRET_KEY=生成: openssl rand -hex 32

# 4. 一键启动
./scripts/deploy.sh

# 5. 查看状态
./scripts/deploy.sh --status
```

### 部署脚本用法

```bash
./deploy.sh              # 启动服务
./deploy.sh --stop     # 停止服务
./deploy.sh --restart   # 重启服务
./deploy.sh --logs     # 查看日志
./deploy.sh --status   # 查看状态
```

### 部署架构

```
┌─────────────────────────────────────────────┐
│                 服务器                       │
│  ┌─────────────────────────────────────┐   │
│  │            Docker Compose            │   │
│  │  ┌──────┐  ┌──────┐  ┌──────────┐  │   │
│  │  │ Nginx │  │ API  │  │  Worker  │  │   │
│  │  │ :80  │  │ :8000│  │  Celery  │  │   │
│  │  └──┬───┘  └──┬───┘  └────┬─────┘  │   │
│  │     │         │           │        │   │
│  │  ┌──┴─────────┴───────────┴────┐   │   │
│  │  │        PostgreSQL :5432      │   │   │
│  │  │        Qdrant    :6333      │   │   │
│  │  │        Neo4j     :7474       │   │   │
│  │  │        Redis     :6379       │   │   │
│  │  └───────────────────────────────┘   │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面 | http://服务器IP |
| API 文档 | http://服务器IP:8000/docs |
| Neo4j Browser | http://服务器IP:7474 |
| Qdrant Dashboard | http://服务器IP:6333/dashboard |

### 构建 Docker 镜像（可选）

如果需要推送到私有仓库：

```bash
./scripts/create-images.sh

# 标记版本
docker tag fengqiao-api:latest registry.example.com/fengqiao-api:v1.0.0
docker tag fengqiao-frontend:latest registry.example.com/fengqiao-frontend:v1.0.0

# 推送
docker push registry.example.com/fengqiao-api:v1.0.0
docker push registry.example.com/fengqiao-frontend:v1.0.0
```

## 测试

```bash
# 后端单元测试
cd knowledge-service
pytest -q tests/

# 端到端测试
./scripts/e2e_smoke_test.py

# 导入测试数据
./scripts/seed_platform_data.py
```

测试账号: `seed@demo.com` / `seed12345`

## 扩展方向

| 方向 | 说明 |
|------|------|
| Reranker | 接入 bge-reranker-v2-m3 提升检索精度 |
| GraphRAG 全局问答 | 社区检测 + 层次摘要 |
| 增量图谱更新 | 监听文档变更，级联清理孤儿实体 |
| WebSocket 多轮对话 | 实时流式输出 + 会话管理 |

## 许可证

MIT
