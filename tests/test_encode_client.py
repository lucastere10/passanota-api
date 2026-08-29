from unittest.mock import MagicMock, patch

import pytest

import app.services.encode_client as encode_client
from app.services.encode_client import OPENAI_EMBEDDINGS_URL, EncodeClientError


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.embeddings_enabled = True
    settings.llm_provider_api_key = "sk-test"
    settings.embedding_model = "text-embedding-3-small"
    settings.embedding_dimensions = 512
    return settings


class FakeClient:
    def __init__(self, response) -> None:
        self.response = response
        self.posted: list[tuple] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None, headers=None):
        self.posted.append((url, json, headers))
        return self.response


@pytest.mark.asyncio
async def test_encode_texts_returns_empty_when_disabled():
    settings = _settings()
    settings.embeddings_enabled = False

    with patch.object(encode_client, "get_settings", return_value=settings):
        result = await encode_client.encode_texts(["arroz"])

    assert result == []


@pytest.mark.asyncio
async def test_encode_texts_requires_api_key():
    settings = _settings()
    settings.llm_provider_api_key = ""

    with patch.object(encode_client, "get_settings", return_value=settings):
        with pytest.raises(EncodeClientError, match="LLM_PROVIDER_API_KEY"):
            await encode_client.encode_texts(["arroz"])


@pytest.mark.asyncio
async def test_encode_texts_calls_openai_embeddings():
    settings = _settings()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": [
            {"index": 1, "embedding": [0.3, 0.4]},
            {"index": 0, "embedding": [0.1, 0.2]},
        ]
    }
    fake = FakeClient(response)

    with (
        patch.object(encode_client, "get_settings", return_value=settings),
        patch.object(encode_client.httpx, "AsyncClient", return_value=fake),
    ):
        result = await encode_client.encode_texts(["arroz", "feijao"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert fake.posted[0][0] == OPENAI_EMBEDDINGS_URL
    assert fake.posted[0][1]["model"] == "text-embedding-3-small"
    assert fake.posted[0][1]["dimensions"] == 512
    assert fake.posted[0][1]["input"] == ["arroz", "feijao"]
    assert fake.posted[0][2]["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_encode_texts_maps_http_error():
    settings = _settings()
    response = MagicMock()
    response.status_code = 429
    response.text = "rate limited"
    fake = FakeClient(response)

    with (
        patch.object(encode_client, "get_settings", return_value=settings),
        patch.object(encode_client.httpx, "AsyncClient", return_value=fake),
    ):
        with pytest.raises(EncodeClientError, match="429"):
            await encode_client.encode_texts(["arroz"])


@pytest.mark.asyncio
async def test_encode_one_maps_failure_to_503():
    from fastapi import HTTPException

    with patch.object(
        encode_client, "encode_texts", side_effect=EncodeClientError("down")
    ):
        with pytest.raises(HTTPException) as exc:
            await encode_client.encode_one("leite")
        assert exc.value.status_code == 503
