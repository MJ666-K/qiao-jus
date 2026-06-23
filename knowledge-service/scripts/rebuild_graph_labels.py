#!/usr/bin/env python3
"""Backfill typed Neo4j labels for existing Entity nodes.

Phase 3 introduced domain-typed extraction (LawArticle, CaseCause,
EvidenceElement, ComplianceObligation, LegalCase). New documents get
multi-label updates via `apoc.create.addLabels` in upsert_entities.
Existing entities created before the upgrade still only have the
generic `:Entity` label.

This script reads every Entity node, inspects its `type` property,
and adds the corresponding typed label (sanitized to Neo4j label rules).
Idempotent: re-running on already-typed nodes is a no-op (Neo4j's
`addLabels` skips existing labels).

Usage:
    cd knowledge-service
    .venv/bin/python scripts/rebuild_graph_labels.py

Requires Neo4j with APOC plugin enabled (already configured in
deploy/docker-compose.yml via NEO4J_PLUGINS: '["apoc"]').
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storage.neo4j_client import get_sync_driver  # noqa: E402

DOMAIN_TYPES = {
    "LawArticle", "CaseCause", "EvidenceElement",
    "ComplianceObligation", "LegalCase",
    "Person", "Organization", "Location", "Date", "Concept",
}


def sanitize_label(raw: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    return cleaned or "Concept"


def main() -> int:
    driver = get_sync_driver()
    with driver.session() as s:
        result = s.run("MATCH (e:Entity) WHERE e.type IS NOT NULL RETURN e.type AS type, count(*) AS n")
        type_counts: dict[str, int] = {}
        for row in result:
            t = row["type"]
            type_counts[t] = type_counts.get(t, 0) + row["n"]

        if not type_counts:
            print("no Entity nodes with type property — nothing to backfill")
            return 0

        print(f"discovered {sum(type_counts.values())} entities across {len(type_counts)} types:")
        for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {t:30s}  {n}")

        print()
        backfilled = 0
        for raw_type, count in type_counts.items():
            label = sanitize_label(raw_type)
            if not label:
                continue
            res = s.run(
                """
                MATCH (e:Entity {type: $type})
                WHERE NOT $label IN labels(e)
                CALL apoc.create.addLabels(e, [$label]) YIELD node
                RETURN count(node) AS updated
                """,
                type=raw_type,
                label=label,
            )
            single = res.single()
            updated = single["updated"] if single else 0
            backfilled += updated
            if updated:
                print(f"  +{updated:6d}  :{label}  (was type={raw_type!r})")

        print()
        print(f"done. {backfilled} entities received typed labels.")
        if backfilled == 0:
            print("(all entities already had their typed labels — no-op)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
