---
name: document
description: "Document processing: upload, parse, chunk, embed, and build graph"
---

# Document Processing

Document processing pipeline: parse -> chunk -> embed -> build graph.

## Input

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| doc_id | string | 是 | 文档 ID |
| file_path | string | 是 | 文件路径 |
| dataset_id | string | 是 | 数据集 ID |
| tenant_id | string | 是 | 租户标识 |
| action | string | 否 | 操作类型: process (默认), reindex |

## Output

```json
{
  "doc_id": "...",
  "status": "done|queued",
  "message": "...",
  "entities_count": 10
}
```

## Workflow (process action)

1. **Parse**: Parse document (PDF/MD/DOCX) to extract text
2. **Chunk**: Split text into parent-child chunks
3. **Embed**: Generate embeddings for chunks
4. **Graph**: Extract entities and relations, build knowledge graph

## Workflow (reindex action)

Triggers async reindexing via Celery worker.

## Example

```python
from skills.document import DocumentSkill

skill = DocumentSkill()
result = await skill.execute({
    "doc_id": "doc-123",
    "file_path": "/path/to/doc.pdf",
    "dataset_id": "ds-456",
    "tenant_id": "tenant-123",
    "action": "process"
})
```
