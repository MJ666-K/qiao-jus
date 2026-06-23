from fastapi import APIRouter
from pydantic import BaseModel

from api.deps import CurrentUserDep
from core.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


class ChunkingConfig(BaseModel):
    chunk_parent_tokens: int
    chunk_child_tokens: int
    chunk_overlap_tokens: int
    search_top_k: int
    rrf_k: int
    rerank_top_k: int


@router.get("/chunking", response_model=ChunkingConfig)
async def get_chunking_config(user: CurrentUserDep):
    return ChunkingConfig(
        chunk_parent_tokens=settings.chunk_parent_tokens,
        chunk_child_tokens=settings.chunk_child_tokens,
        chunk_overlap_tokens=settings.chunk_overlap_tokens,
        search_top_k=settings.search_top_k,
        rrf_k=settings.rrf_k,
        rerank_top_k=settings.rerank_top_k,
    )


@router.put("/chunking", response_model=ChunkingConfig)
async def update_chunking_config(payload: ChunkingConfig, user: CurrentUserDep):
    if user.role != "admin" and "admin" not in user.scopes:
        from fastapi import HTTPException
        raise HTTPException(403, "admin role required")
    settings.chunk_parent_tokens = payload.chunk_parent_tokens
    settings.chunk_child_tokens = payload.chunk_child_tokens
    settings.chunk_overlap_tokens = payload.chunk_overlap_tokens
    settings.search_top_k = payload.search_top_k
    settings.rrf_k = payload.rrf_k
    settings.rerank_top_k = payload.rerank_top_k
    return payload
