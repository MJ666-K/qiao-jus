# 枫桥智诉

**枫桥智诉** 是一套 AI 法律智能辅助平台，面向基层调解、中小企业与普通用户，提供文档管理、混合检索 RAG、知识图谱、结构化报告生成与多轮智能问答。核心理念：**让 AI 依法说话，让普通人看得懂法**。

---

## 产品能力

| 能力 | 说明 |
|------|------|
| **我的文档** | 上传合同/材料（PDF、Word、Markdown），自动解析、切块、向量化 |
| **生成报告** | 基于用户文档生成含风险点、法条引用、建议的结构化分析报告 |
| **我的助手** | 创建专属助手，绑定知识库与报告，多会话流式问答 |
| **知识图谱** | LLM 抽取实体关系，Neo4j 存储，可视化浏览与图谱检索 |
| **混合检索** | Dense（向量）+ BM25 + RRF 融合 + qwen3-rerank 重排 |
| **系统配置** | 在线调整切块、检索、重排、大模型温度等参数（管理员） |

---

## 项目结构

```
qiao-jus/
├── frontend/                 # Vue 3 前端 SPA
├── knowledge-service/        # FastAPI 后端 + Celery Worker
├── deploy/                   # Docker Compose 生产部署
│   ├── app/                  # 前端构建产物（Nginx 静态根目录）
│   ├── data/                 # Postgres / Qdrant / Neo4j / Redis 持久化
│   ├── nginx/                # 反向代理配置
│   ├── .env                  # 生产环境变量
│   └── scripts/              # deploy.sh / bootstrap_user.sh 等
├── docs/                     # 示例数据、申报文档
├── 操作说明文档.md           # 部署、使用、运维、FAQ
├── 技术说明文档.md           # 架构、选型、模块技术细节
└── README.md                 # 本文件（项目说明）
```

---

## 快速开始

### 生产部署（推荐）

```bash
# 1. 配置
cp deploy/.env.example deploy/.env
# 编辑：LLM_API_KEY、JWT_SECRET_KEY、OSS_* 等

# 2. 一键部署
cd deploy
chmod +x scripts/*.sh
./scripts/deploy.sh

# 3. 创建首个管理员
./scripts/bootstrap_user.sh
```

浏览器访问 `http://<服务器IP>/`，使用 `seed@demo.com` / `seed12345` 登录（需先执行 bootstrap）。

| 入口 | 地址 |
|------|------|
| 前端 | `http://<IP>/` |
| API 文档 | `http://<IP>/api/docs` |

对外仅暴露 **80 端口**（Nginx）。数据目录：`deploy/data/`。

### 本地开发

```bash
# 后端
cd knowledge-service
cp .env.example .env
uv venv --python 3.12 .venv && uv pip install -e .
./scripts/start.sh

# 前端
cd frontend
npm install && npm run dev
```

| 入口 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API | http://localhost:8000/docs |

> 本地用 `knowledge-service/.env`（`localhost`）；生产用 `deploy/.env`（Docker 服务名 `postgres`、`redis` 等）。

---

## 技术栈摘要

| 类别 | 技术 |
|------|------|
| 前端 | Vue 3、Element Plus、Pinia、Vite、D3 |
| 后端 | FastAPI、SQLAlchemy、Celery、LiteLLM |
| 存储 | PostgreSQL、Qdrant、Neo4j、Redis、阿里云 OSS |
| 模型 | DashScope：Qwen 对话、text-embedding-v3、qwen3-rerank |
| 部署 | Docker Compose、Nginx |

---

## 部署架构

```
浏览器 → Nginx (:80)
           ├─ 静态文件 (deploy/app/)
           └─ /api、/ws → api 容器 (FastAPI)
                              ├─ worker 容器 (Celery)
                              ├─ postgres / qdrant / neo4j / redis
                              └─ DashScope API + 阿里云 OSS
```

`api` 与 `worker` 共用镜像 `fengqiao-api:latest`，分别处理 HTTP 与异步文档流水线。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [操作说明文档.md](操作说明文档.md) | 功能操作、部署运维、常见问题 |
| [技术说明文档.md](技术说明文档.md) | 架构图、选型理由、各模块技术介绍 |
| [knowledge-service/README.md](knowledge-service/README.md) | 后端 API、目录结构、测试命令 |

---

## 许可证与联系

项目申报与背景说明见 `docs/枫桥智诉项目申报书.md`。
