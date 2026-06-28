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
    SpendOverTimeByCategoryPoint,
    SpendOverTimeByCategoryResponse,
    SpendOverTimeResponse,
    StackedBreakdownItem,
    StackedBreakdownResponse,
    StackedSegment,
    TimeSeriesPoint,
    TopProductItem,
    TopProductsResponse,
)
from app.schemas.invoice import decimal_to_str, invoice_to_response
from app.services.invoice_service import resolve_period


class DashboardService:
    def _period_filters(
        self, period_start: datetime, period_end: datetime, empresa_id: uuid.UUID | None = None
    ):
        filters = [
            Invoice.created_at >= period_start,
            Invoice.created_at <= period_end,
        ]
        if empresa_id:
            filters.append(Invoice.empresa_id == empresa_id)
        return and_(*filters)

    def _base_filters(
        self, period_start: datetime, period_end: datetime, empresa_id: uuid.UUID | None = None
    ):
        filters = [
            Invoice.status == InvoiceStatus.PARSED,
            Invoice.created_at >= period_start,
            Invoice.created_at <= period_end,
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
        period_filters = self._period_filters(period_start, period_end, empresa_id)
        parsed_filters = self._base_filters(period_start, period_end, empresa_id)

        count_result = await db.execute(
            select(func.count(Invoice.id)).where(period_filters)
        )
        invoice_count = int(count_result.scalar_one())

        spend_result = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(parsed_filters)
        )
        total_spend = Decimal(str(spend_result.scalar_one()))

        duration = period_end - period_start
        prev_end = period_start
        prev_start = period_start - duration
        prev_parsed_filters = self._base_filters(prev_start, prev_end, empresa_id)

        prev_result = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(prev_parsed_filters)
        )
        prev_total = Decimal(str(prev_result.scalar_one()))
        change_pct = None
        if prev_total > 0:
            change_pct = float(((total_spend - prev_total) / prev_total) * 100)

        parsed_count_result = await db.execute(
            select(func.count(Invoice.id)).where(parsed_filters)
        )
        parsed_count = int(parsed_count_result.scalar_one())
        avg_ticket = total_spend / parsed_count if parsed_count else Decimal("0")

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
        category_slug: str | None = None,
    ) -> SpendOverTimeResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        trunc_unit = {"day": "day", "week": "week", "month": "month"}.get(granularity, "day")

        if category_slug:
            empresa_filter = "AND i.empresa_id = :empresa_id" if empresa_id else ""
            query = text(
                f"""
                SELECT date_trunc(:trunc_unit, i.created_at) AS bucket,
                       COALESCE(SUM(ii.total_price), 0) AS amount,
                       COUNT(DISTINCT i.id) AS count
                FROM invoices i
                JOIN invoice_items ii ON ii.invoice_id = i.id
                JOIN categories c ON c.id = ii.category_id
                WHERE i.status = 'parsed'
                  AND i.created_at >= :period_start
                  AND i.created_at <= :period_end
                  AND c.slug = :category_slug
                  {empresa_filter}
                GROUP BY bucket
                ORDER BY bucket
                """
            )
            params: dict = {
                "trunc_unit": trunc_unit,
                "period_start": period_start,
                "period_end": period_end,
                "category_slug": category_slug,
            }
            if empresa_id:
                params["empresa_id"] = str(empresa_id)
            result = await db.execute(query, params)
        else:
            empresa_filter = "AND empresa_id = :empresa_id" if empresa_id else ""
            query = text(
                f"""
                SELECT date_trunc(:trunc_unit, created_at) AS bucket,
                       COALESCE(SUM(total_amount), 0) AS amount,
                       COUNT(id) AS count
                FROM invoices
                WHERE status = 'parsed'
                  AND created_at >= :period_start
                  AND created_at <= :period_end
                  {empresa_filter}
                GROUP BY bucket
                ORDER BY bucket
                """
            )
            params = {
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

    async def spend_over_time_by_category(
        self,
        db: AsyncSession,
        period: str = "30d",
        granularity: str = "day",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> SpendOverTimeByCategoryResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        trunc_unit = {"day": "day", "week": "week", "month": "month"}.get(granularity, "day")
        empresa_filter = "AND i.empresa_id = :empresa_id" if empresa_id else ""

        query = text(
            f"""
            SELECT date_trunc(:trunc_unit, i.created_at) AS bucket,
                   COALESCE(c.name, 'Outros') AS category_name,
                   COALESCE(c.slug, 'outros') AS category_slug,
                   COALESCE(SUM(ii.total_price), 0) AS amount
            FROM invoices i
            JOIN invoice_items ii ON ii.invoice_id = i.id
            LEFT JOIN categories c ON c.id = ii.category_id
            WHERE i.status = 'parsed'
              AND i.created_at >= :period_start
              AND i.created_at <= :period_end
              {empresa_filter}
            GROUP BY bucket, c.name, c.slug
            ORDER BY bucket, amount DESC
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

        by_date: dict[str, list[StackedSegment]] = {}
        categories_set: set[str] = set()
        for row in result:
            date_key = row.bucket.date().isoformat()
            cat_label = row.category_name
            categories_set.add(cat_label)
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(
                StackedSegment(
                    label=cat_label,
                    slug=row.category_slug,
                    amount=decimal_to_str(Decimal(str(row.amount))) or "0.00",
                )
            )

        categories = sorted(categories_set)
        points = [
            SpendOverTimeByCategoryPoint(date=date_key, segments=by_date[date_key])
            for date_key in sorted(by_date.keys())
        ]
        return SpendOverTimeByCategoryResponse(points=points, categories=categories)

    async def top_emitters(
        self,
        db: AsyncSession,
        period: str = "30d",
        limit: int = 10,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
        category_slug: str | None = None,
    ) -> BreakdownResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        filters = self._base_filters(period_start, period_end, empresa_id)

        if category_slug:
            result = await db.execute(
                select(
                    func.coalesce(Emitter.trade_name, Emitter.legal_name, Emitter.cnpj).label("label"),
                    func.coalesce(func.sum(InvoiceItem.total_price), 0).label("amount"),
                    func.count(func.distinct(Invoice.id)).label("count"),
                )
                .select_from(Invoice)
                .join(Emitter, Invoice.emitter_id == Emitter.id)
                .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
                .join(Category, InvoiceItem.category_id == Category.id)
                .where(filters, Category.slug == category_slug)
                .group_by(Emitter.id, Emitter.trade_name, Emitter.legal_name, Emitter.cnpj)
                .order_by(func.sum(InvoiceItem.total_price).desc())
                .limit(limit)
            )
        else:
            result = await db.execute(
                select(
                    func.coalesce(Emitter.trade_name, Emitter.legal_name, Emitter.cnpj).label("label"),
                    func.coalesce(func.sum(Invoice.total_amount), 0).label("amount"),
                    func.count(Invoice.id).label("count"),
                )
                .select_from(Invoice)
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

    async def top_emitters_by_category(
        self,
        db: AsyncSession,
        period: str = "30d",
        limit: int = 10,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> StackedBreakdownResponse:
        period_start, period_end = resolve_period(period, date_from, date_to)
        filters = self._base_filters(period_start, period_end, empresa_id)

        top_result = await db.execute(
            select(
                Emitter.id,
                func.coalesce(Emitter.trade_name, Emitter.legal_name, Emitter.cnpj).label("label"),
                func.coalesce(func.sum(InvoiceItem.total_price), 0).label("total"),
            )
            .select_from(Invoice)
            .join(Emitter, Invoice.emitter_id == Emitter.id)
            .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
            .where(filters)
            .group_by(Emitter.id, Emitter.trade_name, Emitter.legal_name, Emitter.cnpj)
            .order_by(func.sum(InvoiceItem.total_price).desc())
            .limit(limit)
        )
        top_rows = top_result.all()
        if not top_rows:
            return StackedBreakdownResponse(items=[], categories=[])

        emitter_ids = [row.id for row in top_rows]
        segment_result = await db.execute(
            select(
                Emitter.id.label("emitter_id"),
                func.coalesce(Category.name, "Outros").label("category_name"),
                func.coalesce(Category.slug, "outros").label("category_slug"),
                func.coalesce(func.sum(InvoiceItem.total_price), 0).label("amount"),
            )
            .select_from(Invoice)
            .join(Emitter, Invoice.emitter_id == Emitter.id)
            .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
            .outerjoin(Category, InvoiceItem.category_id == Category.id)
            .where(filters, Emitter.id.in_(emitter_ids))
            .group_by(Emitter.id, Category.name, Category.slug)
        )

        segments_by_emitter: dict[uuid.UUID, list[StackedSegment]] = {}
        categories_set: set[str] = set()
        for row in segment_result:
            cat_label = row.category_name
            categories_set.add(cat_label)
            segments_by_emitter.setdefault(row.emitter_id, []).append(
                StackedSegment(
                    label=cat_label,
                    slug=row.category_slug,
                    amount=decimal_to_str(Decimal(str(row.amount))) or "0.00",
                )
            )

        categories = sorted(categories_set)
        items = [
            StackedBreakdownItem(
                label=row.label,
                total=decimal_to_str(Decimal(str(row.total))) or "0.00",
                segments=sorted(
                    segments_by_emitter.get(row.id, []),
                    key=lambda s: Decimal(s.amount),
                    reverse=True,
                ),
            )
            for row in top_rows
        ]
        return StackedBreakdownResponse(items=items, categories=categories)

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
                func.coalesce(Category.slug, "outros").label("slug"),
                func.coalesce(func.sum(InvoiceItem.total_price), 0).label("amount"),
                func.count(InvoiceItem.id).label("count"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .outerjoin(Category, InvoiceItem.category_id == Category.id)
            .where(filters)
            .group_by(Category.name, Category.slug)
            .order_by(func.sum(InvoiceItem.total_price).desc())
        )
        rows = result.all()
        total = sum(Decimal(str(row.amount)) for row in rows) or Decimal("0")

        items = [
            BreakdownItem(
                label=row.label,
                slug=row.slug,
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
            .options(
                selectinload(Invoice.emitter),
                selectinload(Invoice.items).selectinload(InvoiceItem.category),
            )
            .where(*filters)
            .order_by(Invoice.issued_at.desc().nullslast(), Invoice.created_at.desc())
            .limit(limit)
        )
        invoices = result.scalars().all()
        return [invoice_to_response(inv).model_dump(mode="json") for inv in invoices]


dashboard_service = DashboardService()
