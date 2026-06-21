---
name: rag_search
description: "Hybrid RAG retrieval: dense vector + BM25 sparse + RRF fusion"
---

# RAG Search

Hybrid search combining dense vectors (Qdrant) + sparse (BM25) + Reciprocal Rank Fusion for accurate legal knowledge retrieval.

## Input

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 检索查询字符串 |
| tenant_id | string | 是 | 租户标识 |
| dataset_id | string | 否 | 数据集过滤 |
| doc_type | string | 否 | 文档类型过滤 (law/case/compliance/contract/dispute) |
| top_k | integer | 否 | 返回结果数量，默认 10 |

## Output

```json
{
  "hits": [
    {
      "chunk_id": "...",
      "text": "...",
      "score": 0.85,
      "source": "...",
      "document_id": "...",
      "metadata": {}
    }
  ],
  "count": 5
}
```

## Workflow

1. Dense search: Query Qdrant vector database with tenant filter
2. Sparse search: BM25 over tenant corpus in Postgres
3. RRF fusion: Combine dense and sparse results using Reciprocal Rank Fusion
4. Fetch parent chunks for context
5. Return top-K results

## Example

```python
from skills.rag_search import RagSearchSkill

skill = RagSearchSkill()
result = await skill.execute({
    "query": "劳动合同法第39条",
    "tenant_id": "tenant-123",
    "top_k": 5
})
```
