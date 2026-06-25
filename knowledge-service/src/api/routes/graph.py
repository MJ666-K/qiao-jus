from fastapi import APIRouter, HTTPException, Query
from uuid import UUID

from api.deps import CurrentUserDep
from pipeline.graph_global import global_answer
from pipeline.graph_query import resolve_graph_entities
from schemas.graph import GraphEdge, GraphNode, GraphQueryRequest, GraphQueryResult, RelationMutation
from storage.neo4j_client import (
    count_entities,
    create_relation,
    delete_relation,
    list_communities_async,
    query_dataset_graph,
)

router = APIRouter(prefix="/graph", tags=["graph"])


def _to_nodes(raw_entities: list[dict]) -> list[GraphNode]:
    seen: set[str] = set()
    nodes: list[GraphNode] = []
    for e in raw_entities:
        eid = e.get("id") or e.get("name")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        nodes.append(
            GraphNode(
                id=eid,
                name=e.get("name", ""),
                type=e.get("type", "concept"),
                description=e.get("description"),
            )
        )
    return nodes


def _to_edges(raw_relations: list[dict]) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for r in raw_relations:
        src, tgt = r.get("source"), r.get("target")
        if not src or not tgt:
            continue
        rtype = r.get("type") or "RELATED"
        key = (src, tgt, rtype)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            GraphEdge(
                source=src,
                target=tgt,
                type=rtype,
                description=r.get("description"),
                weight=float(r.get("weight") or 1),
            )
        )
    return edges


@router.get("/dataset", response_model=GraphQueryResult)
async def dataset_graph(
    user: CurrentUserDep,
    dataset_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
):
    """Load the full relationship graph scoped to one knowledge dataset."""
    res = await query_dataset_graph(str(user.tenant_id), str(dataset_id), limit=limit)
    return GraphQueryResult(
        entities=_to_nodes(res.get("entities", [])),
        relations=_to_edges(res.get("relations", [])),
        related_chunks=[],
    )


@router.post("/local", response_model=GraphQueryResult)
async def local(payload: GraphQueryRequest, user: CurrentUserDep):
    ds = str(payload.dataset_id) if payload.dataset_id else None
    res = await resolve_graph_entities(
        payload.query, user.tenant_id, payload.depth, limit=50, dataset_id=ds
    )
    raw_entities = (res or {}).get("entities", [])
    raw_relations = (res or {}).get("relations", [])
    raw_chunks = (res or {}).get("chunks", [])
    return GraphQueryResult(
        entities=_to_nodes(raw_entities),
        relations=_to_edges(raw_relations),
        related_chunks=raw_chunks,
    )


@router.post("/relations", response_model=GraphEdge)
async def add_relation(payload: RelationMutation, user: CurrentUserDep):
    try:
        await create_relation(
            user.tenant_id,
            payload.source,
            payload.target,
            payload.type,
            payload.description or "",
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return GraphEdge(
        source=payload.source,
        target=payload.target,
        type=payload.type,
        description=payload.description,
    )


@router.delete("/relations")
async def remove_relation(
    user: CurrentUserDep,
    source: str,
    target: str,
):
    deleted = await delete_relation(user.tenant_id, source, target)
    if not deleted:
        raise HTTPException(404, "relation not found")
    return {"status": "ok"}


@router.get("/stats")
async def graph_stats(user: CurrentUserDep):
    """Tenant-level graph entity count for UI hints."""
    total = await count_entities(user.tenant_id)
    return {"entity_count": total}


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
