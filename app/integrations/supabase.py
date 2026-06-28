import asyncio
from functools import lru_cache

import httpx
from supabase import Client, create_client

from app.config import get_settings


class SupabaseConfigError(Exception):
    pass


class SupabaseAuthError(Exception):
    pass


@lru_cache
def get_supabase_admin() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SupabaseConfigError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def _auth_api_key() -> str:
    settings = get_settings()
    return settings.supabase_secret_key or settings.supabase_publishable_key


async def verify_access_token(token: str) -> dict:
    """Valida JWT do usuário via Auth API (modelo atual, sem JWT secret local)."""
    settings = get_settings()
    api_key = _auth_api_key()
    if not settings.supabase_url or not api_key:
        raise SupabaseConfigError("Supabase auth is not configured")

    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            url,
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {token}",
            },
        )

    if response.status_code != 200:
        raise SupabaseAuthError("Invalid or expired token")

    return response.json()


async def upload_storage_object(
    bucket: str,
    path: str,
    data: bytes,
    content_type: str = "image/jpeg",
) -> str:
    def _upload() -> str:
        client = get_supabase_admin()
        client.storage.from_(bucket).upload(
            path,
            data,
            {"content-type": content_type, "upsert": "true"},
        )
        return path

    return await asyncio.to_thread(_upload)


async def create_signed_storage_url(
    bucket: str,
    path: str,
    expires_in: int = 3600,
) -> str | None:
    def _sign() -> str | None:
        settings = get_settings()
        client = get_supabase_admin()
        result = client.storage.from_(bucket).create_signed_url(path, expires_in)
        signed_url = result.get("signedURL") or result.get("signedUrl")
        if not signed_url:
            return None
        if signed_url.startswith("http"):
            return signed_url
        return f"{settings.supabase_url.rstrip('/')}/storage/v1{signed_url}"

    return await asyncio.to_thread(_sign)


async def download_storage_object(bucket: str, path: str) -> bytes:
    def _download() -> bytes:
        client = get_supabase_admin()
        return client.storage.from_(bucket).download(path)

    return await asyncio.to_thread(_download)


def _list_storage_prefix_sync(bucket: str, prefix: str) -> list[str]:
    client = get_supabase_admin()
    storage = client.storage.from_(bucket)
    normalized = prefix.rstrip("/")
    paths: list[str] = []

    def walk(current: str) -> None:
        items = storage.list(current or None)
        if not items:
            return
        for item in items:
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
            if not name:
                continue
            full_path = f"{current}/{name}" if current else name
            item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            if item_id is None:
                walk(full_path)
            else:
                paths.append(full_path)

    walk(normalized)
    return paths


async def list_storage_prefix(bucket: str, prefix: str) -> list[str]:
    return await asyncio.to_thread(_list_storage_prefix_sync, bucket, prefix)


async def delete_storage_objects(bucket: str, paths: list[str]) -> int:
    if not paths:
        return 0

    def _delete() -> int:
        client = get_supabase_admin()
        client.storage.from_(bucket).remove(paths)
        return len(paths)

    return await asyncio.to_thread(_delete)


def _extract_link_properties(response: object) -> dict:
    properties = getattr(response, "properties", None)
    if properties is None and isinstance(response, dict):
        properties = response.get("properties")
    if isinstance(properties, dict):
        return properties
    if properties is None:
        return {}
    hashed_token = getattr(properties, "hashed_token", None)
    return {"hashed_token": hashed_token} if hashed_token else {}


async def generate_magic_link(email: str, callback_url: str) -> str:
    """Build a PKCE-compatible magic link using hashed_token + server-side verifyOtp."""

    def _generate() -> str:
        from urllib.parse import urlencode

        client = get_supabase_admin()
        response = client.auth.admin.generate_link(
            {
                "type": "magiclink",
                "email": email,
            }
        )
        properties = _extract_link_properties(response)
        token_hash = properties.get("hashed_token")
        if not token_hash:
            raise SupabaseAuthError("Failed to generate magic link")
        base = callback_url.split("?")[0].rstrip("/")
        query = urlencode({"token_hash": token_hash, "type": "magiclink"})
        return f"{base}?{query}"

    return await asyncio.to_thread(_generate)
