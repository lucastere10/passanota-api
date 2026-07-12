from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import InvoiceSource, InvoiceStatus


class EmitterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cnpj: str | None = None
    trade_name: str | None = None
    legal_name: str | None = None
    city: str | None = None
    uf: str | None = None
    address: dict | None = None


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    line_number: int
    product_code: str | None = None
    description: str
    ncm: str | None = None
    ean: str | None = None
    quantity: str | None = None
    unit: str | None = None
    unit_price: str | None = None
    total_price: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    category_slug: str | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID | None = None
    source_type: InvoiceSource
    access_key: str | None = None
    uf: str | None = None
    model: int
    series: str | None = None
    number: str | None = None
    issued_at: datetime | None = None
    total_amount: str | None = None
    discount_amount: str | None = None
    qr_url: str | None = None
    protocol: str | None = None
    photo_original_path: str | None = None
    photo_processed_path: str | None = None
    ai_model: str | None = None
    ai_confidence: str | None = None
    extracted_at: datetime | None = None
    status: InvoiceStatus
    error_message: str | None = None
    created_at: datetime
    emitter: EmitterResponse | None = None
    items: list[InvoiceItemResponse] = []


class ExtractionSummary(BaseModel):
    fornecedor: str | None = None
    data: str | None = None
    item_count: int = 0


class CaptureInvoiceResponse(BaseModel):
    invoice: InvoiceResponse
    processed_image_url: str | None = None
    preprocess_skipped: bool = False
    extraction_summary: ExtractionSummary
    processing_note: str = (
        "Nota recebida. O processamento com IA roda em segundo plano — "
        "acompanhe o status pela lista de notas ou pelo ID retornado."
    )


class PaginatedInvoicesResponse(BaseModel):
    data: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class UpdateInvoiceRequest(BaseModel):
    issued_at: datetime | None = None
    total_amount: str | None = None
    discount_amount: str | None = None
    emitter_name: str | None = None


class UpdateInvoiceItemRequest(BaseModel):
    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    total_price: str | None = None
    unit: str | None = None
    category_id: UUID | None = None


def str_to_decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(value)


def decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def invoice_item_to_response(item) -> InvoiceItemResponse:
    category_name = item.category.name if item.category else None
    category_slug = item.category.slug if item.category else None
    return InvoiceItemResponse(
        id=item.id,
        line_number=item.line_number,
        product_code=item.product_code,
        description=item.description,
        ncm=item.ncm,
        ean=item.ean,
        quantity=decimal_to_str(item.quantity),
        unit=item.unit,
        unit_price=decimal_to_str(item.unit_price),
        total_price=decimal_to_str(item.total_price),
        category_id=item.category_id,
        category_name=category_name,
        category_slug=category_slug,
    )


def invoice_to_response(invoice) -> InvoiceResponse:
    items = [invoice_item_to_response(item) for item in invoice.items]

    emitter = None
    if invoice.emitter:
        emitter = EmitterResponse.model_validate(invoice.emitter)

    return InvoiceResponse(
        id=invoice.id,
        empresa_id=invoice.empresa_id,
        source_type=invoice.source_type,
        access_key=invoice.access_key,
        uf=invoice.uf,
        model=invoice.model,
        series=invoice.series,
        number=invoice.number,
        issued_at=invoice.issued_at,
        total_amount=decimal_to_str(invoice.total_amount),
        discount_amount=decimal_to_str(invoice.discount_amount),
        qr_url=invoice.qr_url,
        protocol=invoice.protocol,
        photo_original_path=invoice.photo_original_path,
        photo_processed_path=invoice.photo_processed_path,
        ai_model=invoice.ai_model,
        ai_confidence=decimal_to_str(invoice.ai_confidence),
        extracted_at=invoice.extracted_at,
        status=invoice.status,
        error_message=invoice.error_message,
        created_at=invoice.created_at,
        emitter=emitter,
        items=items,
    )
