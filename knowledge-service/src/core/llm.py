import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = logging.getLogger(__name__)


def _common_kwargs() -> dict[str, Any]:
    return {
        "api_key": settings.llm_api_key,
        "api_base": settings.llm_api_url,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    resp = litellm.embedding(
        model=f"openai/{settings.embedding_model_id}",
        input=texts,
        **_common_kwargs(),
    )
    return [d["embedding"] for d in resp.data]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    response_json: bool = False,
    max_tokens: int | None = None,
) -> str:
    # `openai/<model>` tells LiteLLM to treat api_base as an OpenAI-compatible
    # endpoint and skip its provider-routing logic. Critical for DashScope /
    # Together / vLLM / any custom OpenAI-compatible server.
    kwargs: dict[str, Any] = {
        "model": f"openai/{settings.llm_model_id}",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        **_common_kwargs(),
    }
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}
    resp = litellm.completion(**kwargs)
    return resp.choices[0].message.content or ""


def chat_json(messages: list[dict[str, str]], *, temperature: float = 0.1) -> Any:
    raw = chat(messages, temperature=temperature, response_json=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def rerank_documents(
    query: str,
    documents: list[str],
    *,
    top_n: int | None = None,
    instruct: str | None = None,
) -> list[tuple[int, float]]:
    """DashScope compatible rerank API. Returns (document_index, relevance_score) in rank order."""
    import httpx

    if not documents:
        return []

    payload: dict[str, Any] = {
        "model": settings.rerank_model_id,
        "query": query,
        "documents": documents,
        "top_n": top_n or len(documents),
    }
    inst = instruct if instruct is not None else settings.rerank_instruct
    if inst:
        payload["instruct"] = inst

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            settings.rerank_api_url,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results")
    if results is None and isinstance(data.get("output"), dict):
        results = data["output"].get("results")
    if not isinstance(results, list):
        raise ValueError(f"unexpected rerank response: {data!r}")

    ranked: list[tuple[int, float]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        try:
            ranked.append((int(item["index"]), float(item["relevance_score"])))
        except (KeyError, TypeError, ValueError):
            continue
    return ranked


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def stream_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    kwargs: dict[str, Any] = {
        "model": f"openai/{settings.llm_model_id}",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        "stream": True,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        **_common_kwargs(),
    }
    resp = await litellm.acompletion(**kwargs)
    async for chunk in resp:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
