# 枫桥智诉 · 平台知识库测试数据

与 [技术架构文档.md](../技术架构文档.md) 对齐的演示数据集，供 RAG + 知识图谱底座导入测试。

## 目录结构

```
docs/data/
├── laws/           法律法规（doc_type=law，按「第X条」切分，1条=1chunk）
├── cases/          典型案例（doc_type=case，512字/段，overlap 64）
├── compliance/     合规条款（doc_type=compliance，256字/段）
└── graph/          图谱关系 CSV（案由→证据要素，供 Neo4j 导入扩展）
```

## 文档格式约定

### 法规 (law)

```markdown
# 法律名称
【法律层级】法律
【领域】劳动

第X条
法条正文……
```

### 类案 (case)

```markdown
# 案例标题
【案由】xxx
【法院】xxx人民法院
【案号】（2024）X01民终123号
【裁判年份】2024

裁判要旨正文……
```

## 导入方式

```bash
# 确保 knowledge-service 已启动
cd knowledge-service
./scripts/seed_platform_data.py

# 可选：指定 API 与账号
KS_API=http://localhost:8000 KS_EMAIL=admin@demo.com KS_PASSWORD=secret ./scripts/seed_platform_data.py
```

导入后会自动创建三个平台知识库：**法规库**、**类案库**、**合规库**，并触发 Celery 入库流水线。

## 切块规则（底座实现）

| doc_type | 切分策略 | 元数据 |
|----------|----------|--------|
| law | 按「第X条」拆分，1条=1 chunk | law_name, article_no, domain, level |
| case | 512 字符滑动窗口，overlap 64 | cause, court, case_no, year |
| compliance | 256 字符滑动窗口，overlap 32 | domain, duty_type |
