"""CLI entrypoint for one-time bootstrap: DB tables, Qdrant collection, Neo4j schema.

Usage: python -m scripts.init_db
"""
import asyncio
import logging

from storage.neo4j_client import ensure_schema
from storage.postgres import init_db
from storage.qdrant_client import ensure_collection


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("init_db")
    log.info("creating postgres tables...")
    await init_db()
    log.info("ensuring qdrant collection...")
    await ensure_collection()
    log.info("ensuring neo4j schema...")
    await ensure_schema()
    log.info("done")


if __name__ == "__main__":
    asyncio.run(main())
