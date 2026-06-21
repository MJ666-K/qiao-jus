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
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    # Cypher forbids parameterized variable-length hops (`*1..$depth`); depth is
    # a validated int from the API schema so f-string interpolation is safe.
    if not isinstance(depth, int) or depth < 1 or depth > 3:
        depth = 2
    keys = [k.strip() for k in (keywords or []) + entities if k and k.strip()]
    if not keys:
        return {"entities": [], "relations": [], "chunks": []}
    # Dedupe while preserving order; prefer longer keywords first for CONTAINS.
    seen: set[str] = set()
    uniq_keys: list[str] = []
    for k in sorted(keys, key=len, reverse=True):
        lk = k.lower()
        if lk not in seen:
            seen.add(lk)
            uniq_keys.append(k)

    cypher = f"""
        MATCH (e:Entity {{tenant_id: $tenant}})
        WHERE any(k IN $keywords WHERE k <> '' AND (
            toLower(e.name) CONTAINS toLower(k)
            OR (size(e.name) >= 4 AND toLower(k) CONTAINS toLower(e.name))
            OR toLower(coalesce(e.description, '')) CONTAINS toLower(k)
        ))
        WITH DISTINCT e
        ORDER BY size(e.name) DESC
        LIMIT $seed_limit
        OPTIONAL MATCH (e)-[:RELATED*1..{depth}]-(neighbor:Entity)
        WHERE neighbor IS NULL OR neighbor.tenant_id = $tenant
        WITH collect(DISTINCT e) + [n IN collect(DISTINCT neighbor) WHERE n IS NOT NULL] AS nodes
        UNWIND nodes AS node
        WITH DISTINCT node
        RETURN collect({{
            id: node.id, name: node.name, type: node.type,
            description: node.description
        }}) AS entities
    """
    driver = get_driver()
    async with driver.session() as s:
        result = await s.run(
            cypher,
            keywords=uniq_keys,
            tenant=tenant_id,
            seed_limit=min(limit, 12),
        )
        record = await result.single()
        if not record:
            return {"entities": [], "relations": [], "chunks": []}
        entities_out = [e for e in (record["entities"] or []) if e and e.get("name")]
        rels = await fetch_relations_among(
            [e["id"] for e in entities_out if e.get("id")], tenant_id
        )
        return {"entities": entities_out[:limit], "relations": rels, "chunks": []}


async def fetch_relations_among(
    entity_ids: list[str],
    tenant_id: str,
) -> list[dict[str, Any]]:
    ids = [i for i in entity_ids if i]
    if not ids:
        return []
    cypher = """
        MATCH (a:Entity {tenant_id: $tenant})-[r:RELATED]->(b:Entity {tenant_id: $tenant})
        WHERE a.id IN $ids AND b.id IN $ids
        RETURN a.id AS source, b.id AS target,
               coalesce(r.type, 'RELATED') AS type,
               r.description AS description,
               coalesce(r.weight, 1.0) AS weight
    """
    driver = get_driver()
    async with driver.session() as s:
        result = await s.run(cypher, ids=ids, tenant=tenant_id)
        rows = await result.data()
        return [
            {
                "source": row["source"],
                "target": row["target"],
                "type": row.get("type") or "RELATED",
                "description": row.get("description"),
                "weight": float(row.get("weight") or 1),
            }
            for row in rows
        ]


async def create_relation(
    tenant_id: str,
    source_id: str,
    target_id: str,
    rel_type: str = "RELATED",
    description: str = "",
) -> None:
    driver = get_driver()
    async with driver.session() as s:
        rec = await s.run(
            """
            MATCH (a:Entity {id: $src, tenant_id: $tenant}),
                  (b:Entity {id: $tgt, tenant_id: $tenant})
            MERGE (a)-[rel:RELATED]->(b)
            SET rel.type = $type, rel.description = $desc,
                rel.weight = coalesce(rel.weight, 0) + 1
            RETURN rel
            """,
            src=source_id,
            tgt=target_id,
            tenant=tenant_id,
            type=rel_type or "RELATED",
            desc=description or "",
        )
        if not await rec.single():
            raise ValueError("entity not found or tenant mismatch")


async def delete_relation(
    tenant_id: str,
    source_id: str,
    target_id: str,
) -> bool:
    driver = get_driver()
    async with driver.session() as s:
        rec = await s.run(
            """
            MATCH (a:Entity {id: $src, tenant_id: $tenant})-[r:RELATED]->(b:Entity {id: $tgt, tenant_id: $tenant})
            WITH collect(r) AS rels
            FOREACH (x IN rels | DELETE x)
            RETURN size(rels) AS deleted
            """,
            src=source_id,
            tgt=target_id,
            tenant=tenant_id,
        )
        row = await rec.single()
        return bool(row and row["deleted"] > 0)


async def local_query_by_chunks(
    chunk_ids: list[str],
    tenant_id: str,
    depth: int = 2,
    limit: int = 50,
) -> dict[str, Any]:
    """Find entities mentioned by chunks (fallback when name match fails)."""
    if not isinstance(depth, int) or depth < 1 or depth > 3:
        depth = 2
    ids = [c for c in chunk_ids if c]
    if not ids:
        return {"entities": [], "relations": [], "chunks": []}
    cypher = f"""
        MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {{tenant_id: $tenant}})
        WHERE c.id IN $chunk_ids
        WITH DISTINCT e
        LIMIT $seed_limit
        OPTIONAL MATCH (e)-[:RELATED*1..{depth}]-(neighbor:Entity)
        WHERE neighbor IS NULL OR neighbor.tenant_id = $tenant
        WITH collect(DISTINCT e) + [n IN collect(DISTINCT neighbor) WHERE n IS NOT NULL] AS nodes
        UNWIND nodes AS node
        WITH DISTINCT node
        RETURN collect({{
            id: node.id, name: node.name, type: node.type,
            description: node.description
        }}) AS entities
    """
    driver = get_driver()
    async with driver.session() as s:
        result = await s.run(
            cypher,
            chunk_ids=ids,
            tenant=tenant_id,
            seed_limit=min(limit, 12),
        )
        record = await result.single()
        if not record:
            return {"entities": [], "relations": [], "chunks": []}
        entities_out = [e for e in (record["entities"] or []) if e and e.get("name")]
        rels = await fetch_relations_among(
            [e["id"] for e in entities_out if e.get("id")], tenant_id
        )
        return {"entities": entities_out[:limit], "relations": rels, "chunks": []}


def sync_seed_cause_evidence(tenant_id: str, rows: list[dict[str, str]]) -> int:
    """Import cause→evidence relations from CSV for predictable graph search."""
    driver = get_sync_driver()
    count = 0
    with driver.session() as s:
        for row in rows:
            cause = (row.get("cause") or "").strip()
            evidence = (row.get("evidence_element") or "").strip()
            desc = (row.get("description") or "").strip()
            if not cause or not evidence:
                continue
            for name, etype in ((cause, "cause"), (evidence, "evidence")):
                s.run(
                    """
                    MERGE (e:Entity {id: $id})
                    SET e.name = $name, e.type = $etype,
                        e.description = coalesce(e.description, '') + $desc,
                        e.tenant_id = $tenant
                    """,
                    id=f"{tenant_id}:{name}",
                    name=name,
                    etype=etype,
                    desc=desc + " " if desc else "",
                    tenant=tenant_id,
                )
            s.run(
                """
                MATCH (src:Entity {id: $src}), (tgt:Entity {id: $tgt})
                MERGE (src)-[rel:RELATED {type: 'requires_evidence'}]->(tgt)
                SET rel.description = $desc, rel.weight = coalesce(rel.weight, 0) + 1
                """,
                src=f"{tenant_id}:{cause}",
                tgt=f"{tenant_id}:{evidence}",
                desc=desc,
            )
            count += 1
    return count


async def count_entities(tenant_id: str) -> int:
    driver = get_driver()
    async with driver.session() as s:
        result = await s.run(
            "MATCH (e:Entity {tenant_id: $tenant}) RETURN count(e) AS c",
            tenant=tenant_id,
        )
        record = await result.single()
        return int(record["c"]) if record else 0


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
