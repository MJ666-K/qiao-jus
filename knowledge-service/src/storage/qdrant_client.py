import logging
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient, QdrantClient, models as qm

from core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None
_sync_client: QdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=False)
    return _client


def get_sync_client() -> QdrantClient:
    global _sync_client
    if _sync_client is None:
        _sync_client = QdrantClient(url=settings.qdrant_url, prefer_grpc=False)
    return _sync_client


async def ensure_collection() -> None:
    client = get_client()
    cols = await client.get_collections()
    names = {c.name for c in cols.collections}
    if settings.qdrant_collection not in names:
        await client.create_collection(
            settings.qdrant_collection,
            vectors_config=qm.VectorParams(
                size=settings.qdrant_vector_size,
                distance=qm.Distance.COSINE,
            ),
        )
    await _ensure_payload_indexes(client)


_PAYLOAD_INDEXES = ["dataset_id", "tenant_id", "document_id", "parent_id", "doc_type", "domain"]


async def _ensure_payload_indexes(client: AsyncQdrantClient) -> None:
    for field in _PAYLOAD_INDEXES:
        try:
            await client.create_payload_index(
                settings.qdrant_collection,
                field_name=field,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            if "already" not in str(e).lower():
                logger.warning("payload index %s: %s", field, e)


async def upsert_points(points: list[dict[str, Any]]) -> None:
    client = get_client()
    await client.upsert(
        settings.qdrant_collection,
        points=[qm.PointStruct(**p) for p in points],
    )


def upsert_points_sync(points: list[dict[str, Any]]) -> None:
    client = get_sync_client()
    client.upsert(
        settings.qdrant_collection,
        points=[qm.PointStruct(**p) for p in points],
    )


async def search_dense(
    vector: list[float],
    filters: dict[str, Any],
    top_k: int,
) -> list[qm.ScoredPoint]:
    client = get_client()
    user_id = filters.pop("_user_scope", None)
    must = [qm.FieldCondition(key=k, match=qm.MatchValue(value=str(v))) for k, v in filters.items()]
    built_filter: qm.Filter | None = None
    if user_id:
        built_filter = qm.Filter(
            must=must,
            should=[
                qm.Filter(
                    must=[qm.FieldCondition(key="scope", match=qm.MatchValue(value="platform"))]
                ),
                qm.Filter(
                    must=[
                        qm.FieldCondition(key="scope", match=qm.MatchValue(value="user")),
                        qm.FieldCondition(key="user_id", match=qm.MatchValue(value=user_id)),
                    ]
                ),
            ],
        )
    elif must:
        built_filter = qm.Filter(must=must)
    result = await client.query_points(
        settings.qdrant_collection,
        query=vector,
        query_filter=built_filter,
        limit=top_k,
        with_payload=True,
    )
    return result.points


async def delete_by_document(document_id: str) -> None:
    client = get_client()
    await client.delete(
        settings.qdrant_collection,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
            )
        ),
    )


def delete_by_document_sync(document_id: str) -> None:
    client = get_sync_client()
    client.delete(
        settings.qdrant_collection,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
            )
        ),
    )


def make_point_id() -> str:
    return str(uuid.uuid4())
