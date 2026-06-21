# Bug 修复日志

本文档记录 knowledge-service 从 v0.1 到 v0.5 期间修复的所有阻塞性 bug，包含原因、症状、修复方案，方便后续维护参考。

## 目录

- [架构层](#架构层)
- [数据层](#数据层)
- [外部依赖层](#外部依赖层)
- [API 层](#api-层)
- [经验教训](#经验教训)

---

## 架构层

### BUG-001: Celery Worker async engine 跨 event loop

**症状**
```
RuntimeError: Task got Future attached to a different loop
```
worker 处理 `chunk_and_embed` 任务时，SQLAlchemy async engine 的连接池绑定到上一次 `asyncio.run()` 创建的 loop，新任务里再使用就抛错。

**根因**
Celery 是同步框架，每个任务跑在独立的 `asyncio.run()` 中。`storage/postgres.py` 的 `engine` 是模块级单例，连接池里的连接绑死在第一次创建时的 loop 上。

**修复**
新增 `storage/postgres_sync.py`，pipeline 全部走 sync 路径（`psycopg2-binary`）。Celery worker 不再用 async engine。API 层保留 async engine。

**关键代码**
```python
# storage/postgres_sync.py
_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2")
sync_engine = create_engine(_sync_db_url, ...)
SyncSessionLocal = sessionmaker(sync_engine, ...)
```

**教训**
Celery 任务里永远用同步 SQLAlchemy，async engine 只能用在长生命周期进程（如 FastAPI）。

---

### BUG-002: Neo4j async driver 同样跨 loop

**症状**
worker 调用 Neo4j 写图谱时偶发 `Future attached to a different loop`。

**根因**
和 BUG-001 同源。Async driver 持有连接池跨 loop。

**修复**
`storage/neo4j_client.py` 同时维护 sync 和 async 两个 driver。worker 用 `get_sync_driver()` + `sync_upsert_entities()` + `sync_delete_by_document()`。

---

### BUG-003: FastAPI lazy-load 触发 MissingGreenlet

**症状**
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called
```
GET `/documents/{id}` 返回 500。

**根因**
代码访问 `doc.dataset.tenant_id`，触发 SQLAlchemy 的 lazy-load 关系，但 async session 不允许在 greenlet 上下文之外做 IO。

**修复**
用 `joinedload` 显式预加载关系：
```python
select(Document).options(joinedload(Document.dataset)).where(...)
```

**教训**
async SQLAlchemy + 关系字段：永远 `joinedload` / `selectinload` 显式加载，别依赖 lazy-load。

---

## 数据层

### BUG-004: Qdrant point id 与 Chunk.id 不一致

**症状**
`/search` 返回 200 但 `hits: []`。Qdrant 有数据，dense 检索也返回 hit，但 `_fetch_chunks_with_parents` 查 Postgres 拿到 0 行。

**根因**
`chunk_and_embed` 用 `make_point_id()` 生成新的 UUID 作为 Qdrant point id，与 `Chunk.id`（Postgres 主键）不同。dense 检索返回的 id 是 Qdrant point id，BM25 返回的是 `Chunk.id`，RRF 融合后查不到对应 chunk。

**修复**
写入 Qdrant 时 `pid = str(c.id)`，让 Qdrant point id == Chunk.id == Chunk.qdrant_id 三者统一。

```python
for c, vec in zip(child_payload, embeddings, strict=True):
    pid = str(c.id)
    c.qdrant_id = uuid.UUID(pid)
    points.append({"id": pid, "vector": vec, "payload": {...}})
```

**教训**
当多个数据源需要在 fusion 层做 ID 匹配时，业务主键必须贯穿所有存储。

---

### BUG-005: Document 模型没有 tenant_id 列

**症状**
`/search` 调用 `_load_corpus` 时：
```
AttributeError: type object 'Document' has no attribute 'tenant_id'
```

**根因**
租户隔离字段在 `Dataset.tenant_id` 上，Document 通过 `dataset_id` 关联。但 `_load_corpus` 直接用 `Document.tenant_id` 做过滤。

**修复**
显式 join Dataset：
```python
select(Chunk).join(Document).join(Dataset).where(Dataset.tenant_id == tenant_id)
```

**教训**
多租户字段位置要一致；查询时必须明确 tenant_id 的真实归属表。

---

### BUG-006: SearchHit schema 不接受 UUID 类型的 chunk_id

**症状**
```
pydantic_core.ValidationError: Input should be a valid string, input_value=UUID('...')
```

**根因**
Postgres 返回的 `parent_id` 是 UUID 对象，但 `SearchHit.chunk_id` 是 `str`。

**修复**
`retrieve_children` 输出时显式 `str(...)`：
```python
parent_key = str(r["parent_id"]) if r["parent_id"] else pid
out.append({"chunk_id": parent_key, ...})
```

---

## 外部依赖层

### BUG-007: unstructured 对 .md 也尝试下载 spaCy 模型

**症状**
```
Failed to download spaCy model from https://github.com/explosion/spacy-models/...
Connection reset by peer
```
所有 .md 文档解析失败。

**根因**
`unstructured` 的 `partition(auto)` 即使 strategy=fast 也会触发某些后端的 spaCy 探测；GitHub 在国内被墙，下载失败抛错。

**修复**
对纯文本格式（.md/.txt/.rst/.json/.yaml）绕过 unstructured，直接读文件：
```python
_TEXT_EXTS = {".md", ".markdown", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml"}
if suffix in _TEXT_EXTS:
    return _parse_text(path)
```

**教训**
国内环境慎用需要 GitHub 下载的库；纯文本格式没必要走重型 NLP pipeline。

---

### BUG-008: Qdrant client 1.18 移除 `search()`

**症状**
```
AttributeError: 'AsyncQdrantClient' object has no attribute 'search'
```

**根因**
Qdrant Python SDK 1.10+ 把 `search()` 标记 deprecated，1.18 完全移除，必须用 `query_points()`。

**修复**
```python
result = await client.query_points(
    settings.qdrant_collection,
    query=vector,
    query_filter=qm.Filter(must=must) if must else None,
    limit=top_k,
    with_payload=True,
)
return result.points
```

---

### BUG-009: passlib + bcrypt 4.x 兼容性 bug

**症状**
```
ValueError: password cannot be longer than 72 bytes, truncate manually if necessary
```
即使密码只有 9 个字符也报错。

**根因**
passlib 在初始化 bcrypt 后端时跑内置的 wrap-bug 检测，使用一个固定 test vector。bcrypt 4.x 对 72 字节限制更严格，把这个测试向量直接拒了。

**修复**
绕过 passlib，直接调用 `bcrypt` 包：
```python
import bcrypt
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")
```

**教训**
生态兼容问题最隐蔽，passlib 已 2 年没大更新；优先用直接依赖。

---

### BUG-010: LiteLLM embedding 不加 `openai/` 前缀报 Provider NOT provided

**症状**
```
BadRequestError: LLM Provider NOT provided. Pass in the LLM provider you are trying to call.
You passed model=text-embedding-v3
```

**根因**
LiteLLM 默认按 model 名做 provider 路由（`gpt-*` → openai，`claude-*` → anthropic）。`text-embedding-v3` 不在已知列表里就抛错。

**修复**
`embed_texts` 和 `chat` 都加 `openai/` 前缀：
```python
litellm.embedding(model=f"openai/{settings.embedding_model_id}", ...)
litellm.completion(model=f"openai/{settings.llm_model_id}", ...)
```

**教训**
自定义 OpenAI-compatible 端点（DashScope/ZhipuAI/vLLM）必须用 `openai/` 前缀 + `api_base`。

---

## API 层

### BUG-011: Cypher list comprehension 语法错误

**症状**
```
Neo.ClientError.Statement.SyntaxError: Invalid input 'FOR'
```

**根因**
在 Cypher 里写 Python 风格的 `[toLower(x) FOR x IN $entities]`，Neo4j 不支持这种语法。

**修复**
用 Cypher 原生语法：
```cypher
WHERE toLower(e.name) IN [x IN $entities | toLower(x)]
```

---

### BUG-012: Cypher 变长跳数不能用参数

**症状**
```
Parameter maps cannot be used in MATCH patterns
```

**根因**
`*1..$depth` 这种参数化的关系跳数 Cypher 不支持。

**修复**
用 f-string 拼（depth 在 API schema 已校验为 int 1-3，无注入风险）：
```python
if not isinstance(depth, int) or depth < 1 or depth > 3:
    depth = 2
cypher = f"MATCH (e)-[:RELATED*1..{depth}]-(neighbor:Entity) ..."
```

---

### BUG-013: extract_entities_relations 短查询被阈值拒绝

**症状**
`/graph/local` 始终返回 `entities: []`，即使图谱里有数据。

**根因**
```python
if len(text.strip()) < 20:
    return [], []
```
查询 "智芯科技 NeuroScale 阿里云" 只有 16 字符，被短路。

**修复**
阈值降到 4。查询本身就短，不能因为短就拒。

---

### BUG-014: graph_context 是 dict 列表被 join 拼接报错

**症状**
```
TypeError: sequence item 0: expected str instance, dict found
```

**根因**
`" | ".join(graph_ctx[:5])` 直接 join dict 列表。

**修复**
```python
graph_strs = [f"{g['name']}({g.get('type','')})" for g in graph_ctx[:5] if isinstance(g, dict)]
context_blocks.append("知识图谱关联实体：" + " | ".join(graph_strs))
```

---

### BUG-015: MCP 拒绝下划线开头的参数名

**症状**
```
mcp.server.fastmcp.exceptions.InvalidSignature:
Parameter __user_token__ of knowledge_search cannot start with '_'
```

**根因**
FastMCP 把 `_` 开头参数当作"私有"参数排除。

**修复**
重命名 `__user_token__` → `user_token`。

---

## 经验教训

### 1. 异步 + 同步混用要明确边界
Celery worker 走 sync，FastAPI 走 async。两套 engine/driver 必须分离开。

### 2. 多存储 ID 必须统一
当业务对象跨多个存储（Postgres + Qdrant + Neo4j），用业务主键（如 Chunk.id）贯穿所有存储，避免每个存储生成自己的 id。

### 3. Cypher 不是 SQL
变量绑定限制多，list comprehension 语法不同，变长跳数不能参数化。每次写完 Cypher 必须 probe。

### 4. 国内网络环境影响技术选型
- GitHub 下载（spaCy 模型、HuggingFace 模型）大概率失败 → 优先选不需要外部下载的方案
- Docker Hub 连不上 → 用国内镜像源
- PyPI 走清华/阿里云镜像

### 5. Pydantic v2 严格模式
所有 schema 字段类型必须严格匹配。UUID 对象传入 str 字段会报错。统一在数据出口处 `str()` 转换。

### 6. 注释纪律
本次开发中所有"为何这样写"的非直觉决策都留了 1-3 行 inline 注释：
- 安全相关（为何 f-string 拼 Cypher 安全）
- 生态兼容（为何绕过 passlib 直接用 bcrypt）
- 框架怪癖（为何 LiteLLM 要 `openai/` 前缀）
- 架构决策（为何 Qdrant point id = Chunk.id）

这些注释是抗离职的，留下能让后续维护者避免重新踩坑。
