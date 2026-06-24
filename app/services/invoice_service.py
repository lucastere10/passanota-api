import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Emitter, Invoice, InvoiceItem, InvoiceSource, InvoiceStatus
from app.schemas.extraction import ExtractedInvoice
from app.services.image.storage import StorageError, invoice_photo_storage
from app.services.task_dispatcher import dispatch_invoice_processing

settings = get_settings()


class InvoiceService:
    async def get_by_id(
        self, db: AsyncSession, invoice_id: uuid.UUID, empresa_id: uuid.UUID | None = None
    ) -> Invoice | None:
        filters = [Invoice.id == invoice_id]
        if empresa_id:
            filters.append(Invoice.empresa_id == empresa_id)
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.emitter), selectinload(Invoice.items))
            .where(*filters)
        )
        return result.scalar_one_or_none()

    async def list_invoices(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        uf: str | None = None,
        emitter_cnpj: str | None = None,
        status: InvoiceStatus | None = None,
        empresa_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
    ) -> tuple[list[Invoice], int]:
        filters = []

        if date_from:
            filters.append(Invoice.issued_at >= date_from)
        if date_to:
            filters.append(Invoice.issued_at <= date_to)
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

        offset = (page - 1) * page_size
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.emitter), selectinload(Invoice.items))
            .where(where_clause)
            .order_by(Invoice.issued_at.desc().nullslast(), Invoice.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def submit_capture(
        self,
        db: AsyncSession,
        image_bytes: bytes,
        empresa_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
        content_type: str = "image/jpeg",
    ) -> Invoice:
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
        await db.refresh(invoice)
        await dispatch_invoice_processing(invoice.id)
        return invoice

    async def populate_from_extraction(
        self,
        db: AsyncSession,
        invoice: Invoice,
        extracted: ExtractedInvoice,
    ) -> None:
        import asyncio

        if extracted.fornecedor:
            emitter = await self._get_or_create_emitter_by_name(db, extracted.fornecedor)
            invoice.emitter_id = emitter.id

        if extracted.data:
            invoice.issued_at = self._parse_date(extracted.data)

        if extracted.total is not None:
            invoice.total_amount = extracted.total

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
            db.add(
                InvoiceItem(
                    invoice_id=invoice.id,
                    line_number=idx + 1,
                    description=item.descricao,
                    quantity=item.quantidade,
                    unit_price=unit_price,
                    total_price=item.valor,
                    embedding=embedding,
                )
            )

    @staticmethod
    def _encode_descriptions(descriptions: list[str]) -> list[list[float]]:
        from app.services.embedding_service import embedding_service

        return embedding_service.encode(descriptions)

    async def _get_or_create_emitter_by_name(self, db: AsyncSession, name: str) -> Emitter:
        normalized = name.strip().upper()
        result = await db.execute(
            select(Emitter).where(func.upper(Emitter.trade_name) == normalized)
        )
        emitter = result.scalar_one_or_none()
        if emitter:
            return emitter

        emitter = Emitter(trade_name=normalized, legal_name=normalized)
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
