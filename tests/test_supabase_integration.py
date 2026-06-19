from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.supabase import SupabaseAuthError, verify_access_token


@pytest.mark.asyncio
async def test_verify_access_token_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")

    from app.config import get_settings

    get_settings.cache_clear()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "a@b.com",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.integrations.supabase.httpx.AsyncClient", return_value=mock_client):
        payload = await verify_access_token("user-jwt-token")

    assert payload["email"] == "a@b.com"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_verify_access_token_invalid(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")

    from app.config import get_settings

    get_settings.cache_clear()

    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.integrations.supabase.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(SupabaseAuthError):
            await verify_access_token("bad-token")

    get_settings.cache_clear()
