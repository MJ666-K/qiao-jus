from fastapi import APIRouter, HTTPException

from api.deps import CurrentUserDep
from pipeline.graph_build import extract_entities_relations
from pipeline.graph_global import global_answer
from schemas.graph import GraphEdge, GraphNode, GraphQueryRequest, GraphQueryResult
from storage.neo4j_client import list_communities_async, local_query

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/local", response_model=GraphQueryResult)
async def local(payload: GraphQueryRequest, user: CurrentUserDep):
    ents, _ = await extract_entities_relations(payload.query)
    if not ents:
        return GraphQueryResult()
    names = [e["name"] for e in ents]
    res = await local_query(
        names,
        tenant_id=user.tenant_id,
        depth=payload.depth,
        limit=50,
    )
    raw_entities = (res or {}).get("entities", [])
    raw_chunks = (res or {}).get("chunks", [])

    seen_entities: set[str] = set()
    nodes: list[GraphNode] = []
    for e in raw_entities:
        eid = e.get("id") or e.get("name")
        if not eid or eid in seen_entities:
            continue
        seen_entities.add(eid)
        nodes.append(
            GraphNode(
                id=eid,
                name=e.get("name", ""),
                type=e.get("type", "concept"),
                description=e.get("description"),
            )
        )

    edges: list[GraphEdge] = []
    return GraphQueryResult(entities=nodes, relations=edges, related_chunks=raw_chunks)


@router.get("/communities")
async def list_communities(user: CurrentUserDep, level: int = 0):
    """List all knowledge-graph communities (clusters) for the tenant."""
    return await list_communities_async(user.tenant_id, level=level)


@router.post("/global")
async def global_query(payload: GraphQueryRequest, user: CurrentUserDep):
    """GraphRAG-style global QA. Best for abstract / cross-document questions.
    Triggers map-reduce over community summaries."""
    result = await global_answer(payload.query, user.tenant_id)
    return result


@router.post("/rebuild")
async def rebuild_communities(user: CurrentUserDep):
    """Rebuild community detection synchronously. Use after bulk imports."""
    try:
        import asyncio
        from pipeline.community import detect_and_write_communities
        stats = await asyncio.to_thread(detect_and_write_communities, user.tenant_id)
        return {"status": "ok", **stats}
    except Exception as e:
        raise HTTPException(500, f"community rebuild failed: {e}") from e
