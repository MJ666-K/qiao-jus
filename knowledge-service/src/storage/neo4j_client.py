import logging
from typing import Any

from neo4j import AsyncGraphDatabase, GraphDatabase

from core.config import settings

logger = logging.getLogger(__name__)

_driver = None
_sync_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
    return _driver


def get_sync_driver():
    global _sync_driver
    if _sync_driver is None:
        _sync_driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
    return _sync_driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


CONSTRAINTS = [
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT community_id IF NOT EXISTS FOR (cm:Community) REQUIRE cm.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
    "CREATE INDEX entity_tenant IF NOT EXISTS FOR (e:Entity) ON (e.tenant_id)",
    "CREATE INDEX community_tenant IF NOT EXISTS FOR (cm:Community) ON (cm.tenant_id)",
]


async def ensure_schema() -> None:
    driver = get_driver()
    async with driver.session() as s:
        for stmt in CONSTRAINTS + INDEXES:
            try:
                await s.run(stmt)
            except Exception as e:
                logger.warning("neo4j schema: %s", e)


async def upsert_entities(
    tenant_id: str,
    dataset_id: str,
    document_id: str,
    chunk_id: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> None:
    driver = get_driver()
    async with driver.session() as s:
        await s.run(
            """
            MERGE (d:Document {id: $doc})
            SET d.tenant_id = $tenant, d.dataset_id = $dataset
            MERGE (c:Chunk {id: $chunk})
            SET c.tenant_id = $tenant, c.document_id = $doc
            MERGE (c)-[:PART_OF]->(d)
            """,
            doc=document_id,
            tenant=tenant_id,
            dataset=dataset_id,
            chunk=chunk_id,
        )
        for e in entities:
            await s.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name = $name, e.type = $type,
                    e.description = coalesce(e.description, '') + coalesce($desc, ''),
                    e.tenant_id = $tenant, e.dataset_id = $dataset
                WITH e
                MATCH (c:Chunk {id: $chunk})
                MERGE (c)-[:MENTIONS]->(e)
                """,
                id=f"{tenant_id}:{e['name']}",
                name=e["name"],
                type=e.get("type", "concept"),
                desc=e.get("description", ""),
                tenant=tenant_id,
                dataset=dataset_id,
                chunk=chunk_id,
            )
        for r in relations:
            src = f"{tenant_id}:{r['source']}"
            tgt = f"{tenant_id}:{r['target']}"
            await s.run(
                """
                MATCH (src:Entity {id: $src}), (tgt:Entity {id: $tgt})
                MERGE (src)-[rel:RELATED {type: $type}]->(tgt)
                SET rel.description = $desc, rel.weight = coalesce(rel.weight, 0) + 1,
                    rel.source_chunk_id = $chunk
                """,
                src=src,
                tgt=tgt,
                type=r.get("type", "RELATED"),
                desc=r.get("description", ""),
                chunk=chunk_id,
            )


async def local_query(
    entities: list[str],
    tenant_id: str,
    depth: int = 2,
    limit: int = 50,
) -> dict[str, Any]:
    # Cypher forbids parameterized variable-length hops (`*1..$depth`); depth is
    # a validated int from the API schema so f-string interpolation is safe.
    if not isinstance(depth, int) or depth < 1 or depth > 3:
        depth = 2
    cypher = f"""
        MATCH (e:Entity)
        WHERE toLower(e.name) IN [x IN $entities | toLower(x)] AND e.tenant_id = $tenant
        OPTIONAL MATCH (e)-[:RELATED*1..{depth}]-(neighbor:Entity)
        WITH e, neighbor
        OPTIONAL MATCH (chunk:Chunk)-[:MENTIONS]->(neighbor)
        RETURN collect(DISTINCT {{
            id: neighbor.id, name: neighbor.name, type: neighbor.type,
            description: neighbor.description
        }}) AS entities,
        collect(DISTINCT {{
            id: chunk.id, document_id: chunk.document_id, text: chunk.text
        }}) AS chunks
        LIMIT $limit
    """
    driver = get_driver()
    async with driver.session() as s:
        result = await s.run(cypher, entities=entities, tenant=tenant_id, limit=limit)
        record = await result.single()
        if not record:
            return {"entities": [], "chunks": []}
        return {"entities": record["entities"], "chunks": record["chunks"]}


async def delete_by_document(document_id: str) -> None:
    driver = get_driver()
    async with driver.session() as s:
        await s.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=document_id)
        await s.run("MATCH (c:Chunk {document_id: $id}) DETACH DELETE c", id=document_id)


def sync_upsert_entities(
    tenant_id: str,
    dataset_id: str,
    document_id: str,
    chunk_id: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> None:
    driver = get_sync_driver()
    with driver.session() as s:
        s.run(
            """
            MERGE (d:Document {id: $doc})
            SET d.tenant_id = $tenant, d.dataset_id = $dataset
            MERGE (c:Chunk {id: $chunk})
            SET c.tenant_id = $tenant, c.document_id = $doc
            MERGE (c)-[:PART_OF]->(d)
            """,
            doc=document_id,
            tenant=tenant_id,
            dataset=dataset_id,
            chunk=chunk_id,
        )
        for e in entities:
            s.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name = $name, e.type = $type,
                    e.description = coalesce(e.description, '') + coalesce($desc, ''),
                    e.tenant_id = $tenant, e.dataset_id = $dataset
                WITH e
                MATCH (c:Chunk {id: $chunk})
                MERGE (c)-[:MENTIONS]->(e)
                """,
                id=f"{tenant_id}:{e['name']}",
                name=e["name"],
                type=e.get("type", "concept"),
                desc=e.get("description", ""),
                tenant=tenant_id,
                dataset=dataset_id,
                chunk=chunk_id,
            )
        for r in relations:
            src = f"{tenant_id}:{r['source']}"
            tgt = f"{tenant_id}:{r['target']}"
            s.run(
                """
                MATCH (src:Entity {id: $src}), (tgt:Entity {id: $tgt})
                MERGE (src)-[rel:RELATED {type: $type}]->(tgt)
                SET rel.description = $desc, rel.weight = coalesce(rel.weight, 0) + 1,
                    rel.source_chunk_id = $chunk
                """,
                src=src,
                tgt=tgt,
                type=r.get("type", "RELATED"),
                desc=r.get("description", ""),
                chunk=chunk_id,
            )


def sync_delete_by_document(document_id: str) -> None:
    driver = get_sync_driver()
    with driver.session() as s:
        s.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=document_id)
        s.run("MATCH (c:Chunk {document_id: $id}) DETACH DELETE c", id=document_id)


def sync_fetch_entity_graph(tenant_id: str) -> dict[str, Any]:
    """Fetch entities + relations for a tenant as adjacency data for community
    detection. Returns {"entities": [{id, name, type}], "relations": [(src_id, tgt_id)]}."""
    driver = get_sync_driver()
    with driver.session() as s:
        ents = s.run(
            "MATCH (e:Entity {tenant_id: $t}) RETURN e.id AS id, e.name AS name, e.type AS type",
            t=tenant_id,
        ).data()
        rels = s.run(
            """
            MATCH (a:Entity {tenant_id: $t})-[:RELATED]->(b:Entity {tenant_id: $t})
            RETURN a.id AS src, b.id AS tgt
            """,
            t=tenant_id,
        ).data()
    return {"entities": ents, "relations": [(r["src"], r["tgt"]) for r in rels]}


def sync_write_communities(
    tenant_id: str, communities: list[dict[str, Any]]
) -> None:
    """Persist communities + entity membership. Each community: {id, level, entities: [entity_id], summary}."""
    driver = get_sync_driver()
    with driver.session() as s:
        # Clear old communities for tenant before rewriting
        s.run(
            "MATCH (cm:Community {tenant_id: $t}) DETACH DELETE cm", t=tenant_id
        )
        for cm in communities:
            s.run(
                """
                MERGE (cm:Community {id: $cid})
                SET cm.tenant_id = $t, cm.level = $level, cm.summary = $summary, cm.title = $title
                """,
                cid=cm["id"],
                t=tenant_id,
                level=cm.get("level", 0),
                summary=cm.get("summary", ""),
                title=cm.get("title", cm.get("summary", "")[:60]),
            )
            for eid in cm["entities"]:
                s.run(
                    """
                    MATCH (cm:Community {id: $cid}), (e:Entity {id: $eid})
                    MERGE (e)-[:MEMBER_OF]->(cm)
                    """,
                    cid=cm["id"],
                    eid=eid,
                )


def sync_list_communities(tenant_id: str, level: int = 0) -> list[dict[str, Any]]:
    driver = get_sync_driver()
    with driver.session() as s:
        rows = s.run(
            """
            MATCH (cm:Community {tenant_id: $t, level: $lvl})
            RETURN cm.id AS id, cm.title AS title, cm.summary AS summary,
                   cm.level AS level
            ORDER BY cm.title
            """,
            t=tenant_id,
            lvl=level,
        ).data()
    return rows


async def list_communities_async(tenant_id: str, level: int = 0) -> list[dict[str, Any]]:
    driver = get_driver()
    async with driver.session() as s:
        result = await s.run(
            """
            MATCH (cm:Community {tenant_id: $t, level: $lvl})
            RETURN cm.id AS id, cm.title AS title, cm.summary AS summary, cm.level AS level
            ORDER BY cm.title
            """,
            t=tenant_id,
            lvl=level,
        )
        records = await result.data()
    return records
