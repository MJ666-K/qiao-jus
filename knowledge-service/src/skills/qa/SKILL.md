---
name: qa
description: "Question answering with RAG + Graph context + LLM generation"
---

# QA

Question answering combining RAG retrieval + Graph context + LLM generation.

## Input

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 用户问题 |
| tenant_id | string | 是 | 租户标识 |
| use_graph | boolean | 否 | 是否使用图谱上下文，默认 true |
| top_k | integer | 否 | 检索数量，默认 8 |

## Output

```json
{
  "query": "违法解除劳动合同怎么赔偿？",
  "answer": "根据《劳动合同法》第39条...",
  "sources": [...],
  "graph_entities": [...]
}
```

## Workflow

1. **Call `rag_search`**: Get relevant chunks via hybrid retrieval
2. **Call `graph_query`** (if use_graph=true): Get knowledge graph entities
3. **Build context**: Combine chunk texts and graph entities
4. **Generate answer**: Use LLM to generate answer with citations

## Skill Composition

This skill calls other skills internally:
- `rag_search`: For document retrieval
- `graph_query`: For knowledge graph context (optional)

## Example

```python
from skills.qa import QASkill

skill = QASkill()
result = await skill.execute({
    "query": "违法解除劳动合同怎么赔偿？",
    "tenant_id": "tenant-123",
    "use_graph": True
})
```
