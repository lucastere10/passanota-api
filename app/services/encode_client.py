import logging

import httpx
from fastapi import HTTPException, status

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
ENCODE_TIMEOUT_SECONDS = 30.0
EMBED_BATCH_SIZE = 100


class EncodeClientError(Exception):
    pass


async def encode_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    if not settings.embeddings_enabled:
        return []
    if not settings.llm_provider_api_key:
        raise EncodeClientError("LLM_PROVIDER_API_KEY is not configured")

    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=ENCODE_TIMEOUT_SECONDS) as client:
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            vectors.extend(await _embed_batch(client, settings, batch))
    return vectors


async def _embed_batch(
    client: httpx.AsyncClient,
    settings: Settings,
    batch: list[str],
) -> list[list[float]]:
    try:
        response = await client.post(
            OPENAI_EMBEDDINGS_URL,
            headers={"Authorization": f"Bearer {settings.llm_provider_api_key}"},
            json={
                "model": settings.embedding_model,
                "input": batch,
                "dimensions": settings.embedding_dimensions,
                "encoding_format": "float",
            },
        )
    except httpx.HTTPError as exc:
        logger.exception("OpenAI embeddings request failed")
        raise EncodeClientError("OpenAI embeddings request failed") from exc

    if response.status_code >= 400:
        logger.error("OpenAI embeddings returned %s: %s", response.status_code, response.text)
        raise EncodeClientError(f"OpenAI embeddings returned {response.status_code}")

    data = response.json().get("data")
    if not isinstance(data, list) or len(data) != len(batch):
        raise EncodeClientError("OpenAI embeddings payload missing vectors")

    ordered = sorted(data, key=lambda item: item.get("index", 0))
    vectors: list[list[float]] = []
    for item in ordered:
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            raise EncodeClientError("OpenAI embeddings payload missing vectors")
        vectors.append(embedding)
    return vectors


async def encode_one(text: str) -> list[float] | None:
    try:
        vectors = await encode_texts([text])
    except EncodeClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de busca semântica indisponível.",
        ) from exc
    return vectors[0] if vectors else None
