from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.deps import CurrentUserDep
from core.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


class RuntimeConfig(BaseModel):
    chunk_parent_tokens: int = Field(ge=200, le=4000)
    chunk_child_tokens: int = Field(ge=50, le=2000)
    chunk_overlap_tokens: int = Field(ge=0, le=200)
    search_top_k: int = Field(ge=1, le=50)
    rrf_k: int = Field(ge=1, le=200)
    rerank_top_k: int = Field(ge=5, le=100)
    bm25_k1: float = Field(ge=0, le=3)
    bm25_b: float = Field(ge=0, le=1)
    dense_top_k_multiplier: int = Field(ge=1, le=10)
    rerank_model_id: str = Field(min_length=1, max_length=128)
    rerank_instruct: str = Field(min_length=1, max_length=2000)
    llm_max_tokens: int = Field(ge=256, le=32000)
    llm_chat_temperature: float = Field(ge=0, le=2)
    llm_stream_temperature: float = Field(ge=0, le=2)
    llm_json_temperature: float = Field(ge=0, le=2)
    llm_suggest_temperature: float = Field(ge=0, le=2)


def _runtime_from_settings() -> RuntimeConfig:
    return RuntimeConfig(
        chunk_parent_tokens=settings.chunk_parent_tokens,
        chunk_child_tokens=settings.chunk_child_tokens,
        chunk_overlap_tokens=settings.chunk_overlap_tokens,
        search_top_k=settings.search_top_k,
        rrf_k=settings.rrf_k,
        rerank_top_k=settings.rerank_top_k,
        bm25_k1=settings.bm25_k1,
        bm25_b=settings.bm25_b,
        dense_top_k_multiplier=settings.dense_top_k_multiplier,
        rerank_model_id=settings.rerank_model_id,
        rerank_instruct=settings.rerank_instruct,
        llm_max_tokens=settings.llm_max_tokens,
        llm_chat_temperature=settings.llm_chat_temperature,
        llm_stream_temperature=settings.llm_stream_temperature,
        llm_json_temperature=settings.llm_json_temperature,
        llm_suggest_temperature=settings.llm_suggest_temperature,
    )


def _apply_runtime(payload: RuntimeConfig) -> None:
    settings.chunk_parent_tokens = payload.chunk_parent_tokens
    settings.chunk_child_tokens = payload.chunk_child_tokens
    settings.chunk_overlap_tokens = payload.chunk_overlap_tokens
    settings.search_top_k = payload.search_top_k
    settings.rrf_k = payload.rrf_k
    settings.rerank_top_k = payload.rerank_top_k
    settings.bm25_k1 = payload.bm25_k1
    settings.bm25_b = payload.bm25_b
    settings.dense_top_k_multiplier = payload.dense_top_k_multiplier
    settings.rerank_model_id = payload.rerank_model_id
    settings.rerank_instruct = payload.rerank_instruct
    settings.llm_max_tokens = payload.llm_max_tokens
    settings.llm_chat_temperature = payload.llm_chat_temperature
    settings.llm_stream_temperature = payload.llm_stream_temperature
    settings.llm_json_temperature = payload.llm_json_temperature
    settings.llm_suggest_temperature = payload.llm_suggest_temperature


def _require_admin(user: CurrentUserDep) -> None:
    if user.role != "admin" and "admin" not in user.scopes:
        raise HTTPException(403, "admin role required")


@router.get("/runtime", response_model=RuntimeConfig)
async def get_runtime_config(user: CurrentUserDep):
    return _runtime_from_settings()


@router.put("/runtime", response_model=RuntimeConfig)
async def update_runtime_config(payload: RuntimeConfig, user: CurrentUserDep):
    _require_admin(user)
    _apply_runtime(payload)
    return payload


# Backward-compatible alias
@router.get("/chunking", response_model=RuntimeConfig)
async def get_chunking_config(user: CurrentUserDep):
    return _runtime_from_settings()


@router.put("/chunking", response_model=RuntimeConfig)
async def update_chunking_config(payload: RuntimeConfig, user: CurrentUserDep):
    _require_admin(user)
    _apply_runtime(payload)
    return payload
