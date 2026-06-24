from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.database import engine
from app.routers import admin, auth, dashboard, devices, empresas, health, internal_tasks, invoices, public, search

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Embeddings carregam sob demanda (primeira busca semântica) para não
    # bloquear o bind do servidor — o download do modelo excede a startup probe.
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

app.include_router(health.router)
app.include_router(auth.router, prefix="/v1")
app.include_router(public.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
app.include_router(empresas.router, prefix="/v1")
app.include_router(devices.router, prefix="/v1")
app.include_router(invoices.router, prefix="/v1")
app.include_router(dashboard.router, prefix="/v1")
app.include_router(search.router, prefix="/v1")
app.include_router(internal_tasks.router)
