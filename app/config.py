from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Garante driver asyncpg para SQLAlchemy async (evita psycopg2)."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "passanota-api"
    debug: bool = False
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@db.[project-ref].supabase.co:5432/postgres"
    )
    api_key: str = Field(
        default="",
        description="Chave de acesso à API do projeto (header X-API-Key)",
    )
    api_key_header: str = "X-API-Key"
    supabase_url: str = ""
    supabase_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
    )
    supabase_publishable_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_ANON_KEY",
        ),
    )
    supabase_storage_bucket: str = "invoice-photos"
    embeddings_enabled: bool = True
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    llm_provider: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_PROVIDER", "AI_PROVIDER"),
    )
    llm_provider_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_PROVIDER_API_KEY", "AI_API_KEY"),
    )
    llm_model: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_MODEL", "AI_MODEL"),
    )
    llm_max_image_bytes: int = Field(
        default=5_242_880,
        validation_alias=AliasChoices("LLM_MAX_IMAGE_BYTES", "AI_MAX_IMAGE_BYTES"),
    )
    resend_api_key: str = ""
    email_from: str = "noreply@passanota.com"
    frontend_url: str = "http://localhost:3000"
    platform_admin_notify_email: str = ""
    platform_admin_email: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        if isinstance(value, str):
            return normalize_database_url(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
