---
name: graph_query
description: "Query knowledge graph: extract entities and traverse neighbors"
---

# Graph Query

Extract entities from query and traverse knowledge graph up to N hops.

## Input

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 查询字符串 |
| tenant_id | string | 是 | 租户标识 |
| depth | integer | 否 | 遍历深度，默认 2 |
| limit | integer | 否 | 最大结果数，默认 50 |

## Output

```json
{
  "entities": [
    {
      "id": "...",
      "name": "劳动合同法第39条",
      "type": "law",
      "description": "..."
    }
  ],
  "relations": [
    {
      "source": "...",
      "target": "...",
      "type": "APPLIES_TO",
      "description": "..."
    }
  ],
  "chunks": [...]
}
```

## Workflow

1. Fast path: Direct keyword match in Neo4j (no LLM)
2. If no hits: Use LLM to extract entities from query
3. Query Neo4j for entity neighbors
4. Fetch related chunks
5. Return entities, relations, and chunks

## Example

```python
from skills.graph_query import GraphQuerySkill

skill = GraphQuerySkill()
result = await skill.execute({
    "query": "物业纠纷",
    "tenant_id": "tenant-123",
    "depth": 2
})
```
