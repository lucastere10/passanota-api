import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.database import engine
from app.routers import admin, auth, categories, dashboard, devices, empresas, health, invoices, public, search

settings = get_settings()
logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("app").setLevel(level)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def _configure_hf_cache() -> None:
    os.environ.setdefault("HF_HOME", settings.hf_home)
    os.makedirs(settings.hf_home, exist_ok=True)


def _warmup_embeddings() -> None:
    from app.services.embedding_service import embedding_service

    embedding_service.load_model()


def mount_routers(application: FastAPI, role: str | None = None) -> None:
    """Attach routers for the process role without importing ML on HTTP."""
    process_role = role or settings.app_role
    application.include_router(health.router)

    if process_role in {"http", "all"}:
        application.include_router(auth.router, prefix="/v1")
        application.include_router(public.router, prefix="/v1")
        application.include_router(admin.router, prefix="/v1")
        application.include_router(empresas.router, prefix="/v1")
        application.include_router(devices.router, prefix="/v1")
        application.include_router(invoices.router, prefix="/v1")
        application.include_router(categories.router, prefix="/v1")
        application.include_router(dashboard.router, prefix="/v1")
        application.include_router(search.router, prefix="/v1")

    if process_role in {"worker", "all"}:
        from app.routers import internal_tasks

        application.include_router(internal_tasks.router)
        application.include_router(internal_tasks.encode_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    if settings.app_role != "http":
        _configure_hf_cache()
    logger.info(
        "API started (role=%s, cloud_tasks=%s, llm_provider=%s, embeddings=%s, hf_home=%s)",
        settings.app_role,
        settings.cloud_tasks_enabled,
        settings.llm_provider or "not set",
        settings.embeddings_enabled,
        settings.hf_home,
    )

    if settings.app_role == "worker" and settings.embeddings_enabled:
        import asyncio

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _warmup_embeddings)

    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

app.add_middleware(SecurityHeadersMiddleware)
mount_routers(app)
