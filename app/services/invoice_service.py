import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Category, Emitter, Invoice, InvoiceItem, InvoiceSource, InvoiceStatus
from app.schemas.extraction import ExtractedInvoice
from app.schemas.invoice import InvoiceStatusItem, str_to_decimal
from app.services.image.storage import StorageError, invoice_photo_storage
from app.services.task_dispatcher import dispatch_invoice_processing

settings = get_settings()


def _invoice_load_options():
    return (
        selectinload(Invoice.emitter),
        selectinload(Invoice.items).selectinload(InvoiceItem.category),
    )


class InvoiceService:
    async def get_by_id(
        self, db: AsyncSession, invoice_id: uuid.UUID, empresa_id: uuid.UUID | None = None
    ) -> Invoice | None:
        filters = [Invoice.id == invoice_id]
        if empresa_id:
            filters.append(Invoice.empresa_id == empresa_id)
        result = await db.execute(
            select(Invoice).options(*_invoice_load_options()).where(*filters)
        )
        return result.scalar_one_or_none()

    async def list_invoices(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        uf: str | None = None,
        emitter_cnpj: str | None = None,
        status: InvoiceStatus | None = None,
        empresa_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Invoice], int]:
        filters = []

        if date_from:
            filters.append(Invoice.issued_at >= date_from)
        if date_to:
            filters.append(Invoice.issued_at <= date_to)
        if created_from:
            filters.append(Invoice.created_at >= created_from)
        if created_to:
            filters.append(Invoice.created_at <= created_to)
        if uf:
            filters.append(Invoice.uf == uf.upper())
        if status:
            filters.append(Invoice.status == status)
        if empresa_id:
            filters.append(Invoice.empresa_id == empresa_id)
        if device_id:
            filters.append(Invoice.device_id == device_id)
        if emitter_cnpj:
            cnpj_digits = "".join(c for c in emitter_cnpj if c.isdigit())
            filters.append(
                Invoice.emitter_id.in_(select(Emitter.id).where(Emitter.cnpj == cnpj_digits))
            )

        where_clause = and_(*filters) if filters else True
        count_result = await db.execute(select(func.count()).select_from(Invoice).where(where_clause))
        total = count_result.scalar_one()

        sort_columns = {
            "created_at": Invoice.created_at,
            "issued_at": Invoice.issued_at,
            "status": Invoice.status,
        }
        sort_column = sort_columns.get(sort_by, Invoice.created_at)
        descending = sort_order != "asc"
        if sort_by == "issued_at":
            primary_order = (
                sort_column.desc().nullslast()
                if descending
                else sort_column.asc().nullsfirst()
            )
        else:
            primary_order = sort_column.desc() if descending else sort_column.asc()

        offset = (page - 1) * page_size
        result = await db.execute(
            select(Invoice)
            .options(*_invoice_load_options())
            .where(where_clause)
            .order_by(primary_order, Invoice.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_statuses(
        self,
        db: AsyncSession,
        invoice_ids: list[uuid.UUID],
        empresa_id: uuid.UUID,
    ) -> list[InvoiceStatusItem]:
        if not invoice_ids:
            return []

        result = await db.execute(
            select(Invoice.id, Invoice.status).where(
                Invoice.id.in_(invoice_ids),
                Invoice.empresa_id == empresa_id,
            )
        )
        return [InvoiceStatusItem(id=row.id, status=row.status) for row in result.all()]

    async def submit_capture(
        self,
        db: AsyncSession,
        image_bytes: bytes,
        empresa_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
        content_type: str = "image/jpeg",
    ) -> Invoice:
        if empresa_id is not None:
            from app.services.admin_service import admin_service

            await admin_service.assert_empresa_can_capture(db, empresa_id)

        if len(image_bytes) > settings.llm_max_image_bytes:
            raise ValueError(
                f"Image exceeds maximum size of {settings.llm_max_image_bytes} bytes"
            )

        invoice = Invoice(
            empresa_id=empresa_id,
            device_id=device_id,
            source_type=InvoiceSource.PHOTO_AI,
            status=InvoiceStatus.PENDING,
        )
        db.add(invoice)
        await db.flush()

        original_path, _processed_path = invoice_photo_storage.build_paths(invoice.id, empresa_id)
        try:
            await invoice_photo_storage.upload(original_path, image_bytes, content_type)
            invoice.photo_original_path = original_path
        except StorageError as exc:
            raise ValueError(f"Failed to store image: {exc}") from exc

        await db.commit()
        await dispatch_invoice_processing(invoice.id)

        result = await db.execute(
            select(Invoice)
            .options(*_invoice_load_options())
            .where(Invoice.id == invoice.id)
        )
        return result.scalar_one()

    async def populate_from_extraction(
        self,
        db: AsyncSession,
        invoice: Invoice,
        extracted: ExtractedInvoice,
    ) -> None:
        import asyncio

        if extracted.fornecedor:
            emitter = await self._get_or_create_emitter(
                db, extracted.fornecedor, cnpj=extracted.cnpj
            )
            invoice.emitter_id = emitter.id

        if extracted.data:
            invoice.issued_at = self._parse_date(extracted.data)

        if extracted.total is not None:
            invoice.total_amount = extracted.total

        category_by_slug = await self._load_category_slug_map(db)

        outros_count = 0
        unmapped_count = 0

        descriptions = [item.descricao for item in extracted.itens]
        embeddings = (
            await asyncio.to_thread(self._encode_descriptions, descriptions)
            if descriptions
            else []
        )

        for idx, item in enumerate(extracted.itens):
            embedding = embeddings[idx] if idx < len(embeddings) else None
            unit_price = None
            if item.quantidade and item.quantidade > 0:
                unit_price = item.valor / item.quantidade

            category_id = None
            if item.categoria:
                category_id = category_by_slug.get(item.categoria)
                if item.categoria == "outros":
                    outros_count += 1
            else:
                unmapped_count += 1

            db.add(
                InvoiceItem(
                    invoice_id=invoice.id,
                    line_number=idx + 1,
                    description=item.descricao,
                    quantity=item.quantidade,
                    unit_price=unit_price,
                    total_price=item.valor,
                    embedding=embedding,
                    category_id=category_id,
                )
            )

        adjusted = self.compute_adjusted_confidence(
            extracted,
            outros_count=outros_count,
            unmapped_count=unmapped_count,
        )
        if adjusted is not None:
            invoice.ai_confidence = Decimal(str(adjusted))

    @staticmethod
    def compute_adjusted_confidence(
        extracted: ExtractedInvoice,
        *,
        outros_count: int,
        unmapped_count: int,
    ) -> float | None:
        if extracted.confianca is None:
            return None

        confidence = float(extracted.confianca)

        if extracted.total and extracted.total > 0 and extracted.itens:
            items_sum = sum(item.valor for item in extracted.itens)
            diff_ratio = abs(float(items_sum - extracted.total)) / float(extracted.total)
            if diff_ratio > 0.05:
                confidence -= 0.15

        total_items = len(extracted.itens)
        if total_items > 0:
            weak_category_count = outros_count + unmapped_count
            if weak_category_count / total_items > 0.30:
                confidence -= 0.10

        return max(0.0, min(1.0, round(confidence, 2)))

    @staticmethod
    def _encode_descriptions(descriptions: list[str]) -> list[list[float]]:
        from app.services.embedding_service import embedding_service

        return embedding_service.encode(descriptions)

    async def _load_category_slug_map(self, db: AsyncSession) -> dict[str, uuid.UUID]:
        result = await db.execute(select(Category.slug, Category.id))
        return {row.slug: row.id for row in result.all()}

    async def _get_or_create_emitter(
        self,
        db: AsyncSession,
        name: str,
        *,
        cnpj: str | None = None,
    ) -> Emitter:
        if cnpj:
            result = await db.execute(select(Emitter).where(Emitter.cnpj == cnpj))
            emitter = result.scalar_one_or_none()
            if emitter:
                return emitter

        normalized = name.strip().upper()
        result = await db.execute(
            select(Emitter).where(func.upper(Emitter.trade_name) == normalized)
        )
        emitter = result.scalar_one_or_none()
        if emitter:
            if cnpj and not emitter.cnpj:
                emitter.cnpj = cnpj
            return emitter

        emitter = Emitter(trade_name=normalized, legal_name=normalized, cnpj=cnpj)
        db.add(emitter)
        await db.flush()
        return emitter

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(value.strip(), fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def delete_invoice(
        self, db: AsyncSession, invoice_id: uuid.UUID, empresa_id: uuid.UUID | None = None
    ) -> bool:
        invoice = await self.get_by_id(db, invoice_id, empresa_id)
        if not invoice:
            return False
        await db.delete(invoice)
        await db.commit()
        return True

    async def update_invoice(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        empresa_id: uuid.UUID | None,
        *,
        issued_at: datetime | None = None,
        total_amount: str | None = None,
        discount_amount: str | None = None,
        emitter_name: str | None = None,
    ) -> Invoice | None:
        invoice = await self.get_by_id(db, invoice_id, empresa_id)
        if not invoice:
            return None

        if issued_at is not None:
            invoice.issued_at = issued_at
        if total_amount is not None:
            invoice.total_amount = str_to_decimal(total_amount)
        if discount_amount is not None:
            invoice.discount_amount = str_to_decimal(discount_amount)
        if emitter_name is not None:
            emitter = await self._get_or_create_emitter(db, emitter_name)
            invoice.emitter_id = emitter.id

        await db.commit()
        return await self.get_by_id(db, invoice_id, empresa_id)

    async def update_invoice_item(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        item_id: uuid.UUID,
        empresa_id: uuid.UUID | None,
        *,
        description: str | None = None,
        quantity: str | None = None,
        unit_price: str | None = None,
        total_price: str | None = None,
        unit: str | None = None,
        category_id: uuid.UUID | None = None,
        category_id_set: bool = False,
    ) -> InvoiceItem | None:
        invoice = await self.get_by_id(db, invoice_id, empresa_id)
        if not invoice:
            return None

        result = await db.execute(
            select(InvoiceItem).where(
                InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        if description is not None:
            item.description = description
        if quantity is not None:
            item.quantity = str_to_decimal(quantity)
        if unit_price is not None:
            item.unit_price = str_to_decimal(unit_price)
        if total_price is not None:
            item.total_price = str_to_decimal(total_price)
        if unit is not None:
            item.unit = unit
        if category_id_set:
            if category_id is not None:
                cat_result = await db.execute(
                    select(Category.id).where(Category.id == category_id)
                )
                if not cat_result.scalar_one_or_none():
                    raise ValueError("Category not found")
            item.category_id = category_id

        await db.commit()
        return item

    async def delete_invoice_item(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        item_id: uuid.UUID,
        empresa_id: uuid.UUID | None = None,
    ) -> bool:
        invoice = await self.get_by_id(db, invoice_id, empresa_id)
        if not invoice:
            return False

        result = await db.execute(
            select(InvoiceItem).where(
                InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return False

        await db.delete(item)
        await db.commit()
        return True


invoice_service = InvoiceService()


def resolve_period(
    period: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)

    if period == "custom" and date_from and date_to:
        return date_from, date_to

    if period == "7d":
        return now - timedelta(days=7), now
    if period == "90d":
        return now - timedelta(days=90), now
    if period == "year":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), now
    if period == "custom" and date_from:
        return date_from, date_to or now

    return now - timedelta(days=30), now
