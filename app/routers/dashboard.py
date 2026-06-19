from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_gestor_or_operador
from app.schemas.auth import AuthContext
from app.schemas.dashboard import (
    BreakdownResponse,
    DashboardSummaryResponse,
    RecentInvoicesResponse,
    SpendOverTimeResponse,
    TopProductsResponse,
)
from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    period: str = Query(default="30d"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> DashboardSummaryResponse:
    return await dashboard_service.summary(db, period, date_from, date_to, empresa_id=auth.empresa_id)


@router.get("/spend-over-time", response_model=SpendOverTimeResponse)
async def spend_over_time(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    period: str = Query(default="30d"),
    granularity: str = Query(default="day"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> SpendOverTimeResponse:
    return await dashboard_service.spend_over_time(
        db, period, granularity, date_from, date_to, empresa_id=auth.empresa_id
    )


@router.get("/top-emitters", response_model=BreakdownResponse)
async def top_emitters(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    period: str = Query(default="30d"),
    limit: int = Query(default=10, ge=1, le=50),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> BreakdownResponse:
    return await dashboard_service.top_emitters(
        db, period, limit, date_from, date_to, empresa_id=auth.empresa_id
    )


@router.get("/top-products", response_model=TopProductsResponse)
async def top_products(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    period: str = Query(default="30d"),
    limit: int = Query(default=20, ge=1, le=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> TopProductsResponse:
    return await dashboard_service.top_products(
        db, period, limit, date_from, date_to, empresa_id=auth.empresa_id
    )


@router.get("/spend-by-category", response_model=BreakdownResponse)
async def spend_by_category(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    period: str = Query(default="30d"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> BreakdownResponse:
    return await dashboard_service.spend_by_category(
        db, period, date_from, date_to, empresa_id=auth.empresa_id
    )


@router.get("/recent", response_model=RecentInvoicesResponse)
async def recent_invoices(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> RecentInvoicesResponse:
    data = await dashboard_service.recent(db, limit, empresa_id=auth.empresa_id)
    return RecentInvoicesResponse(data=data)
