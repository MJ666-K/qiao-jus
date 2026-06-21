from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings

# Sync engine for Celery worker. Celery is fundamentally synchronous; using an
# async engine inside tasks crosses event loops (the engine's connection pool
# binds to one loop, but each task runs in a fresh asyncio.run). Sync avoids this.
_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2")
if "+psycopg2" not in _sync_db_url:
    _sync_db_url = _sync_db_url.replace("postgresql://", "postgresql+psycopg2://")

sync_engine = create_engine(
    _sync_db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False, class_=Session)


def get_sync_session() -> Iterator[Session]:
    with SyncSessionLocal() as session:
        yield session
