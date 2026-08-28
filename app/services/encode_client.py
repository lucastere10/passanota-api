import asyncio
import logging

import httpx
from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)

ENCODE_TIMEOUT_SECONDS = 30.0


class EncodeClientError(Exception):
    pass


def _fetch_id_token(audience: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.fetch_id_token(Request(), audience)


async def encode_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    if not settings.uses_remote_encode:
        from app.services.embedding_service import embedding_service

        return await asyncio.to_thread(embedding_service.encode, texts)

    base = settings.task_handler_base_url.rstrip("/")
    if not base:
        raise EncodeClientError("TASK_HANDLER_BASE_URL is not configured")

    url = f"{base}/internal/encode"
    token = await asyncio.to_thread(_fetch_id_token, url)

    try:
        async with httpx.AsyncClient(timeout=ENCODE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                json={"texts": texts},
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.HTTPError as exc:
        logger.exception("Worker encode request failed")
        raise EncodeClientError("Worker encode request failed") from exc

    if response.status_code >= 400:
        logger.error("Worker encode returned %s: %s", response.status_code, response.text)
        raise EncodeClientError(f"Worker encode returned {response.status_code}")

    data = response.json()
    vectors = data.get("vectors")
    if not isinstance(vectors, list):
        raise EncodeClientError("Worker encode payload missing vectors")
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
