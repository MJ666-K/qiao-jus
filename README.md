# 枫桥智诉 · 法律智能辅助平台

法律智能辅助平台，提供合同审查、纠纷研判、证据指引、RAG 检索和知识图谱等能力。

## 技术架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           用户浏览器                                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                         Vue 3 SPA                                    │
│                     (frontend/src/views/)                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP / WebSocket
┌───────────────────────────────▼─────────────────────────────────────┐
│                     knowledge-service                                │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI REST API                          │   │
│  │   /search  /graph/*  /documents/*  /datasets/*  /auth/*    │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                        │
│  ┌─────────────────────────▼───────────────────────────────────┐   │
│  │                      Skills 模块层                             │   │
│  │   rag_search  │  graph_query  │  qa  │  document            │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                        │
│  ┌─────────────────────────▼───────────────────────────────────┐   │
│  │                    Pipeline / Celery                          │   │
│  │   parse_document  │  chunk_and_embed  │  build_graph          │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                        │
│  ┌─────────────────────────▼───────────────────────────────────┐   │
│  │                      Retrieve 层                               │   │
│  │   hybrid_search (dense+sparse+RRF)  │  reranker              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  PostgreSQL  │  │    Qdrant    │  │        Neo4j            │  │
│  │   元数据     │  │   向量存储    │  │      知识图谱            │  │
│  │  + BM25     │  │   (embedding) │  │   (实体/关系/社区)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心模块实现

### 1. 文档处理流水线 (Pipeline)

```
用户上传文档 (PDF/MD/DOCX)
         │
         ▼
┌─────────────────┐
│  parse_document │  ← unstructured 解析，提取文本
└────────┬────────┘
         │ text
         ▼
┌─────────────────┐
│ chunk_and_embed │  ← 父子切分 + Embedding 生成
└────────┬────────┘
         │ chunks + vectors
         ▼
┌─────────────────┐
│   build_graph  │  ← LLM 抽取实体/关系 → Neo4j
└────────┬────────┘
         │
         ▼
   PostgreSQL     ← 存储 chunk 元数据
   Qdrant         ← 存储向量
   Neo4j          ← 存储实体/关系
```

**关键代码**: `src/pipeline/tasks.py`

### 2. 混合检索 (Hybrid Retrieval)

RAG 检索 = **Dense Search** + **Sparse Search** + **RRF 融合** + **Rerank**

```
用户查询
    │
    ├──► Dense Search ──► Qdrant 向量检索 (cosine similarity)
    │
    ├──► Sparse Search ──► BM25 关键词检索 (PostgreSQL)
    │
    ▼
RRF 融合 (Reciprocal Rank Fusion)
   score = Σ 1/(k + rank)
    │
    ▼
Reranker ──► LLM 重排 (可选)
    │
    ▼
Top-K 结果返回
```

**Dense Search (向量检索)**
- 使用 DashScope `text-embedding-v3` 生成 1024 维向量
- 存入 Qdrant，支持余弦相似度检索
- 按 `tenant_id` 隔离

**Sparse Search (BM25)**
- 纯关键词检索，不依赖向量模型
- 中文按字符分词，英文按单词分词
- 在 PostgreSQL 全文索引上执行

**RRF 融合**
- 将 Dense 和 Sparse 的排名分数合并
- 对两种检索方式的差异鲁棒

**关键代码**: `src/retrieve/hybrid.py`

### 3. 知识图谱 (Knowledge Graph)

**图谱构建**

```
文档文本
    │
    ▼
LLM 实体关系抽取 (extract_entities_relations)
    │
    ├──► entities: [{name, type, description}]
    └──► relations: [{source, target, type, description}]
    │
    ▼
Neo4j 存储
    ├──► Entity 节点 (tenant_id + name 唯一)
    ├──► Chunk 节点 (关联文档)
    └──► MENTIONS / PART_OF / RELATED 关系
```

**实体抽取 Prompt**
```
你是一个严谨的信息抽取引擎，从给定文本中抽取实体和实体关系，
输出严格 JSON。实体 name 用规范全称，去除代词；
关系必须有 source/target/type；description 简洁客观，不超过 50 字。
```

**图谱查询 (Local Search)**

```
用户查询
    │
    ├──► 快速路径: 直接按关键词匹配 Neo4j
    │
    └──► LLM 路径:
         │
         ├──► extract_entities_relations (LLM 抽取实体)
         │
         ├──► local_query (Neo4j 多跳查询)
         │    depth=2: 实体 → 邻居 → 邻居的邻居
         │
         └──► local_query_by_chunks (通过 Chunk 关联查询)
```

**关键代码**:
- `src/pipeline/graph_build.py` - 实体关系抽取
- `src/pipeline/graph_query.py` - 图谱查询
- `src/storage/neo4j_client.py` - Neo4j 操作

### 4. 问答系统 (QA with RAG + Graph)

```
用户问题
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 1. Hybrid 检索 (retrieve_children)                     │
│    → 获取 Top-8 相关文档块                           │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│ 2. 图谱查询 (resolve_graph_entities)                │
│    → 获取关联实体 (depth=2)                         │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│ 3. 上下文组装                                      │
│    → 文档块文本 + 图谱实体                          │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│ 4. LLM 生成                                        │
│    system: "你是知识库问答助手。严格依据上下文作答。"   │
│    user: "问题：{query}\n\n上下文：{context}"       │
└──────────────────────────────────────────────────────┘
                           │
                           ▼
                        答案 + 引用
```

**关键代码**: `src/api/routes/search.py` (answer 接口)

### 5. Skill 模块化架构

每个功能封装为独立 Skill，支持组合调用：

```
skills/
├── base.py              # Skill 基类 (含 call_skill)
├── registry.py          # Skill 注册中心
│
├── rag_search/         # RAG 检索 Skill
│   └── runner.py       # 调用 hybrid.retrieve_children
│
├── graph_query/        # 图谱查询 Skill
│   └── runner.py       # 调用 graph_query.resolve_graph_entities
│
└── qa/                 # 问答 Skill (组合调用)
    └── runner.py       # call_skill("rag_search") + call_skill("graph_query")
```

**Skill 基类**

```python
class Skill(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, params: dict) -> dict:
        pass

    async def call_skill(self, skill_name: str, params: dict) -> dict:
        """组合调用其他 Skill"""
        other = self._registry.get(skill_name)
        return await other.execute(params)
```

**MCP Server 集成**

MCP Server 从 SkillRegistry 动态注册所有 Skill 为 MCP tools:
- `rag_search` → `knowledge_search`
- `graph_query` → `knowledge_graph_query`
- `qa` → `knowledge_answer`

## 数据存储

### PostgreSQL

存储业务元数据和 BM25 索引：

```
documents          ← 文档元数据
document_chunks    ← 文本块 (parent-child)
datasets           ← 数据集
communities        ← 图谱社区
```

### Qdrant

向量数据库，存储文档 embedding：

```
Collection: chunks
├── id: chunk_id
├── vector: 1024 维 embedding
└── payload: {tenant_id, dataset_id, doc_type, text, ...}
```

### Neo4j

图数据库，存储实体关系：

```
(:Entity)         ← 实体节点 (tenant_id:name 唯一)
(:Chunk)          ← 文档块节点
(:Document)       ← 文档节点
(:Community)       ← 社区节点

(:Chunk)-[:MENTIONS]->(:Entity)
(:Chunk)-[:PART_OF]->(:Document)
(:Entity)-[:RELATED|APPLIES_TO|...]->(:Entity)
```

## API 路由

| 路由 | 说明 |
|------|------|
| `POST /search` | Hybrid RAG 检索 |
| `POST /search/answer` | 问答 (RAG + Graph + LLM) |
| `POST /graph/local` | 图谱局部遍历 |
| `POST /graph/global` | GraphRAG 全局问答 |
| `POST /graph/rebuild` | 重建社区 |
| `GET/POST /documents/*` | 文档管理 |
| `GET/POST /datasets/*` | 数据集管理 |

## 项目结构

```
knowledge-service/
├── src/
│   ├── api/
│   │   ├── main.py          # FastAPI 入口
│   │   └── routes/          # REST 路由
│   │       ├── search.py    # 检索/问答 API
│   │       ├── graph.py     # 图谱 API
│   │       └── documents.py  # 文档 API
│   │
│   ├── skills/              # Skill 模块
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── rag_search/
│   │   ├── graph_query/
│   │   ├── qa/
│   │   └── document/
│   │
│   ├── pipeline/             # Celery 流水线
│   │   ├── tasks.py         # 任务定义
│   │   ├── graph_build.py  # 实体关系抽取
│   │   ├── graph_query.py   # 图谱查询
│   │   └── community.py      # 社区检测
│   │
│   ├── retrieve/            # 检索模块
│   │   ├── hybrid.py       # 混合检索
│   │   ├── bm25.py          # BM25 实现
│   │   └── reranker.py     # 重排
│   │
│   ├── storage/             # 存储适配
│   │   ├── postgres.py
│   │   ├── qdrant_client.py
│   │   └── neo4j_client.py
│   │
│   └── core/                 # 核心
│       ├── config.py
│       ├── llm.py           # LLM 调用
│       └── security.py      # JWT 鉴权

frontend/
├── src/
│   ├── views/               # 页面
│   │   ├── SearchView.vue  # 检索页
│   │   ├── GraphView.vue   # 图谱页
│   │   ├── ChatView.vue    # 问答页
│   │   └── ...
│   ├── components/
│   │   └── GraphCanvas.vue # D3 图谱可视化
│   └── api/                # API 客户端
```

## 快速开始

```bash
# 1. 启动后端
cd knowledge-service
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY
uv venv --python 3.12 .venv
uv pip install -e .
./scripts/start.sh

# 2. 启动前端
cd frontend
npm install
npm run dev

# 3. 打开浏览器
# http://localhost:5173
```

## 扩展方向

| 功能 | 实现位置 |
|------|----------|
| Reranker | `src/retrieve/reranker.py` |
| 全局 GraphRAG | `src/pipeline/graph_global.py` |
| 增量图谱更新 | `src/storage/neo4j_client.py` |
| WebSocket 多轮对话 | `src/api/routes/` (待扩展) |
