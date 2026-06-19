import uuid

from app.config import get_settings
from app.integrations.supabase import (
    SupabaseConfigError,
    create_signed_storage_url,
    upload_storage_object,
)

settings = get_settings()


class StorageError(Exception):
    pass


class InvoicePhotoStorage:
    def __init__(self) -> None:
        self._bucket = settings.supabase_storage_bucket

    def _require_config(self) -> None:
        if not settings.supabase_url or not settings.supabase_secret_key:
            raise StorageError("Supabase storage is not configured (SUPABASE_SECRET_KEY)")

    def build_paths(self, invoice_id: uuid.UUID, empresa_id: uuid.UUID | None = None) -> tuple[str, str]:
        prefix = str(empresa_id) if empresa_id else "default"
        base = f"{prefix}/{invoice_id}"
        return f"{base}/original.jpg", f"{base}/processed.jpg"

    async def upload(self, path: str, data: bytes, content_type: str = "image/jpeg") -> str:
        self._require_config()
        try:
            return await upload_storage_object(self._bucket, path, data, content_type)
        except SupabaseConfigError as exc:
            raise StorageError(str(exc)) from exc
        except Exception as exc:
            raise StorageError(f"Upload failed: {exc}") from exc

    async def create_signed_url(self, path: str, expires_in: int = 3600) -> str | None:
        self._require_config()
        try:
            return await create_signed_storage_url(self._bucket, path, expires_in)
        except SupabaseConfigError:
            return None
        except Exception:
            return None


invoice_photo_storage = InvoicePhotoStorage()
