import sys
from unittest.mock import MagicMock, patch

import pytest

import app.services.encode_client as encode_client
from app.services.encode_client import EncodeClientError


@pytest.mark.asyncio
async def test_encode_texts_uses_local_model_when_not_http_role():
    mock_service = MagicMock()
    mock_service.encode.return_value = [[0.1, 0.2]]
    mock_module = MagicMock(embedding_service=mock_service)
    settings = MagicMock(uses_remote_encode=False)

    with (
        patch.object(encode_client, "get_settings", return_value=settings),
        patch.dict(sys.modules, {"app.services.embedding_service": mock_module}),
    ):
        result = await encode_client.encode_texts(["arroz"])

    assert result == [[0.1, 0.2]]
    mock_service.encode.assert_called_once_with(["arroz"])


@pytest.mark.asyncio
async def test_encode_texts_calls_worker_when_http_role():
    settings = MagicMock()
    settings.uses_remote_encode = True
    settings.task_handler_base_url = "https://passanota-worker.example.run.app"

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"vectors": [[0.3, 0.4]]}

    class FakeClient:
        def __init__(self) -> None:
            self.posted: list[tuple] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None, headers=None):
            self.posted.append((url, json, headers))
            return response

    fake = FakeClient()

    with (
        patch.object(encode_client, "get_settings", return_value=settings),
        patch.object(encode_client, "_fetch_id_token", return_value="tok"),
        patch.object(encode_client.httpx, "AsyncClient", return_value=fake),
    ):
        result = await encode_client.encode_texts(["feijao"])

    assert result == [[0.3, 0.4]]
    assert fake.posted[0][0] == "https://passanota-worker.example.run.app/internal/encode"
    assert fake.posted[0][2]["Authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_encode_one_maps_worker_failure_to_503():
    from fastapi import HTTPException

    with patch.object(
        encode_client, "encode_texts", side_effect=EncodeClientError("down")
    ):
        with pytest.raises(HTTPException) as exc:
            await encode_client.encode_one("leite")
        assert exc.value.status_code == 503
