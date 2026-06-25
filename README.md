# 枫桥智诉

AI 法律智能辅助平台：文档管理、混合检索 RAG、知识图谱、报告生成与智能问答。

## 项目结构

```
qiao-jus/
├── frontend/              Vue 3 前端
├── knowledge-service/     FastAPI 后端 + Celery 异步任务
├── deploy/                Docker Compose 生产部署
├── docs/                  示例数据与申报文档
└── 说明文档.md            检索 / 重排 / 模型说明
```

## 本地开发

**1. 配置环境**

```bash
cp knowledge-service/.env.example knowledge-service/.env
# 编辑 .env：必填 LLM_API_KEY、JWT_SECRET_KEY
```

**2. 启动后端**（依赖 Docker：Postgres / Qdrant / Neo4j / Redis）

```bash
cd knowledge-service
uv venv --python 3.12 .venv && uv pip install -e .
./scripts/start.sh
```

**3. 启动前端**

```bash
cd frontend
npm install && npm run dev
```

浏览器打开 http://localhost:5173

| 入口 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |

## 一键部署（Docker）

```bash
cp deploy/.env.example deploy/.env
# 填入 LLM_API_KEY、JWT_SECRET_KEY、OSS 等（连接串已用 Docker 内网服务名）

cd deploy
chmod +x scripts/*.sh
./scripts/deploy.sh
```

> **注意**：`deploy/.env` 用容器服务名（`postgres`、`redis` 等）；本地开发用 `knowledge-service/.env`（`localhost`）。

| 入口 | 地址 |
|------|------|
| 前端 | http://localhost |
| API | http://localhost:8000/docs |

`api` 与 `worker` 共用同一镜像：`api` 处理接口，`worker` 跑文档解析与图谱构建等后台任务。

数据持久化在 `deploy/data/`，前端静态文件在 `deploy/app/`（nginx 根目录）。停止：`cd deploy && docker compose down`

## 技术栈

- **前端**：Vue 3、Element Plus、Pinia
- **后端**：FastAPI、SQLAlchemy、Celery
- **存储**：PostgreSQL、Qdrant、Neo4j、Redis、阿里云 OSS
- **模型**：DashScope（Qwen 对话 / text-embedding-v3 向量 / qwen3-rerank 重排）

## 更多文档

- 后端细节：[knowledge-service/README.md](knowledge-service/README.md)
- 检索与重排：[说明文档.md](说明文档.md)
