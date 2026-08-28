from app.config import Settings, normalize_database_url


def test_normalize_postgresql_to_asyncpg():
    url = "postgresql://user:pass@host:5432/db"
    assert normalize_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normalize_postgres_scheme():
    url = "postgres://user:pass@host:5432/db"
    assert normalize_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_preserve_existing_asyncpg():
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    assert normalize_database_url(url) == url


def test_app_role_http_uses_remote_encode():
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        app_role="http",
        _env_file=None,
    )
    assert settings.is_http_process is True
    assert settings.allows_inline_ml is False
    assert settings.uses_remote_encode is True


def test_app_role_all_allows_inline_ml():
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        app_role="all",
        _env_file=None,
    )
    assert settings.allows_inline_ml is True
    assert settings.uses_remote_encode is False
