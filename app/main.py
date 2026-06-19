from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.routers import admin, auth, dashboard, devices, empresas, health, invoices, public, search

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.embeddings_enabled:
        from app.services.embedding_service import embedding_service

        embedding_service.load_model()
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/v1")
app.include_router(public.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
app.include_router(empresas.router, prefix="/v1")
app.include_router(devices.router, prefix="/v1")
app.include_router(invoices.router, prefix="/v1")
app.include_router(dashboard.router, prefix="/v1")
app.include_router(search.router, prefix="/v1")
