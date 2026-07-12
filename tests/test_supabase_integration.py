import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from app.integrations.supabase import SupabaseAuthError, _token_cache, verify_access_token

JWT_SECRET = "test-jwt-secret-for-unit-tests"


def _make_token(*, sub: str = "550e8400-e29b-41d4-a716-446655440000", email: str = "a@b.com") -> str:
    return jwt.encode(
        {
            "sub": sub,
            "email": email,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def clear_token_cache():
    _token_cache.clear()
    yield
    _token_cache.clear()


@pytest.mark.asyncio
async def test_verify_access_token_local_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)

    from app.config import get_settings

    get_settings.cache_clear()

    token = _make_token()
    payload = await verify_access_token(token)

    assert payload["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["email"] == "a@b.com"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_verify_access_token_local_invalid(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)

    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(SupabaseAuthError):
        await verify_access_token("not-a-valid-jwt")

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_verify_access_token_remote_fallback(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
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
async def test_verify_access_token_remote_invalid(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
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
