import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Category, Emitter, Invoice, InvoiceItem, InvoiceStatus
from app.schemas.dashboard import (
    BreakdownItem,
    BreakdownResponse,
    DashboardSummaryResponse,
    SpendOverTimeResponse,
    TimeSeriesPoint,
    TopProductItem,
    TopProductsResponse,
)
from app.schemas.invoice import decimal_to_str, invoice_to_response
from app.services.invoice_service import resolve_period


class DashboardService:
    def _base_filters(
        self, period_start: datetime, period_end: datetime, empresa_id: uuid.UUID | None = None
    ):
        filters = [
            Invoice.status == InvoiceStatus.PARSED,
            Invoice.issued_at.is_not(None),
            Invoice.issued_at >= period_start,
            Invoice.issued_at <= period_end,
        ]
        if empresa_id:
            filters.append(Invoice.empresa_id == empresa_id)
        return and_(*filters)

    async def summary(
        self,
        db: AsyncSession,
        period: str = "30d",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> DashboardSummaryResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        filters = self._base_filters(period_start, period_end, empresa_id)

        result = await db.execute(
            select(
                func.coalesce(func.sum(Invoice.total_amount), 0),
                func.count(Invoice.id),
            ).where(filters)
        )
        total_spend, invoice_count = result.one()
        total_spend = Decimal(str(total_spend))
        invoice_count = int(invoice_count)
        avg_ticket = total_spend / invoice_count if invoice_count else Decimal("0")

        duration = period_end - period_start
        prev_end = period_start
        prev_start = period_start - duration
        prev_filters = self._base_filters(prev_start, prev_end, empresa_id)

        prev_result = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(prev_filters)
        )
        prev_total = Decimal(str(prev_result.scalar_one()))
        change_pct = None
        if prev_total > 0:
            change_pct = float(((total_spend - prev_total) / prev_total) * 100)

        return DashboardSummaryResponse(
            total_spend=decimal_to_str(total_spend) or "0.00",
            invoice_count=invoice_count,
            avg_ticket=decimal_to_str(avg_ticket.quantize(Decimal("0.01"))) or "0.00",
            period_start=period_start,
            period_end=period_end,
            change_pct=change_pct,
        )

    async def spend_over_time(
        self,
        db: AsyncSession,
        period: str = "30d",
        granularity: str = "day",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> SpendOverTimeResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        trunc_unit = {"day": "day", "week": "week", "month": "month"}.get(granularity, "day")

        empresa_filter = "AND empresa_id = :empresa_id" if empresa_id else ""
        query = text(
            f"""
            SELECT date_trunc(:trunc_unit, issued_at) AS bucket,
                   COALESCE(SUM(total_amount), 0) AS amount,
                   COUNT(id) AS count
            FROM invoices
            WHERE status = 'parsed'
              AND issued_at IS NOT NULL
              AND issued_at >= :period_start
              AND issued_at <= :period_end
              {empresa_filter}
            GROUP BY bucket
            ORDER BY bucket
            """
        )
        params: dict = {
            "trunc_unit": trunc_unit,
            "period_start": period_start,
            "period_end": period_end,
        }
        if empresa_id:
            params["empresa_id"] = str(empresa_id)
        result = await db.execute(query, params)

        points = [
            TimeSeriesPoint(
                date=row.bucket.date().isoformat(),
                amount=decimal_to_str(Decimal(str(row.amount))) or "0.00",
                count=int(row.count),
            )
            for row in result
        ]
        return SpendOverTimeResponse(points=points)

    async def top_emitters(
        self,
        db: AsyncSession,
        period: str = "30d",
        limit: int = 10,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> BreakdownResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        filters = self._base_filters(period_start, period_end, empresa_id)

        result = await db.execute(
            select(
                func.coalesce(Emitter.trade_name, Emitter.legal_name, Emitter.cnpj).label("label"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("amount"),
                func.count(Invoice.id).label("count"),
            )
            .join(Emitter, Invoice.emitter_id == Emitter.id)
            .where(filters)
            .group_by(Emitter.id, Emitter.trade_name, Emitter.legal_name, Emitter.cnpj)
            .order_by(func.sum(Invoice.total_amount).desc())
            .limit(limit)
        )
        rows = result.all()
        total = sum(Decimal(str(row.amount)) for row in rows) or Decimal("0")

        items = [
            BreakdownItem(
                label=row.label,
                amount=decimal_to_str(Decimal(str(row.amount))) or "0.00",
                percentage=float((Decimal(str(row.amount)) / total) * 100) if total else 0.0,
                count=int(row.count),
            )
            for row in rows
        ]
        return BreakdownResponse(items=items)

    async def top_products(
        self,
        db: AsyncSession,
        period: str = "30d",
        limit: int = 20,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> TopProductsResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        filters = self._base_filters(period_start, period_end, empresa_id)

        result = await db.execute(
            select(
                InvoiceItem.description,
                func.coalesce(func.sum(InvoiceItem.quantity), 0).label("total_quantity"),
                func.coalesce(func.sum(InvoiceItem.total_price), 0).label("total_amount"),
                func.count(InvoiceItem.id).label("purchase_count"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(filters)
            .group_by(InvoiceItem.description)
            .order_by(func.sum(InvoiceItem.total_price).desc())
            .limit(limit)
        )

        items = [
            TopProductItem(
                description=row.description,
                total_quantity=decimal_to_str(Decimal(str(row.total_quantity))) or "0",
                total_amount=decimal_to_str(Decimal(str(row.total_amount))) or "0.00",
                purchase_count=int(row.purchase_count),
            )
            for row in result
        ]
        return TopProductsResponse(items=items)

    async def spend_by_category(
        self,
        db: AsyncSession,
        period: str = "30d",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> BreakdownResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        filters = self._base_filters(period_start, period_end, empresa_id)

        result = await db.execute(
            select(
                func.coalesce(Category.name, "Outros").label("label"),
                func.coalesce(func.sum(InvoiceItem.total_price), 0).label("amount"),
                func.count(InvoiceItem.id).label("count"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .outerjoin(Category, InvoiceItem.category_id == Category.id)
            .where(filters)
            .group_by(Category.name)
            .order_by(func.sum(InvoiceItem.total_price).desc())
        )
        rows = result.all()
        total = sum(Decimal(str(row.amount)) for row in rows) or Decimal("0")

        items = [
            BreakdownItem(
                label=row.label,
                amount=decimal_to_str(Decimal(str(row.amount))) or "0.00",
                percentage=float((Decimal(str(row.amount)) / total) * 100) if total else 0.0,
                count=int(row.count),
            )
            for row in rows
        ]
        return BreakdownResponse(items=items)

    async def recent(
        self, db: AsyncSession, limit: int = 10, empresa_id: uuid.UUID | None = None
    ) -> list[dict]:
        filters = [Invoice.status == InvoiceStatus.PARSED]
        if empresa_id:
            filters.append(Invoice.empresa_id == empresa_id)
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.emitter), selectinload(Invoice.items))
            .where(*filters)
            .order_by(Invoice.issued_at.desc().nullslast(), Invoice.created_at.desc())
            .limit(limit)
        )
        invoices = result.scalars().all()
        return [invoice_to_response(inv).model_dump(mode="json") for inv in invoices]


dashboard_service = DashboardService()
