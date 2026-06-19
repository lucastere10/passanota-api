from app.config import normalize_database_url


def test_normalize_postgresql_to_asyncpg():
    url = "postgresql://user:pass@host:5432/db"
    assert normalize_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normalize_postgres_scheme():
    url = "postgres://user:pass@host:5432/db"
    assert normalize_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_preserve_existing_asyncpg():
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    assert normalize_database_url(url) == url
