from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_capture_context, get_db_session, require_gestor_or_operador
from app.models import Dispositivo, InvoiceStatus
from app.schemas.auth import AuthContext, CaptureContext
from app.schemas.invoice import (
    CaptureInvoiceResponse,
    ExtractionSummary,
    InvoiceItemResponse,
    InvoiceResponse,
    InvoiceStatusesResponse,
    PaginatedInvoicesResponse,
    UpdateInvoiceItemRequest,
    UpdateInvoiceRequest,
    invoice_to_response,
)
from app.services.device_service import device_service
from app.services.invoice_service import invoice_service

router = APIRouter(prefix="/invoices", tags=["invoices"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/capture", response_model=CaptureInvoiceResponse, status_code=status.HTTP_202_ACCEPTED)
async def capture_invoice(
    capture_ctx: Annotated[CaptureContext, Depends(get_capture_context)],
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> CaptureInvoiceResponse:
    content_type = file.content_type or "image/jpeg"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported content type: {content_type}",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty image file",
        )

    try:
        invoice = await invoice_service.submit_capture(
            db,
            image_bytes,
            empresa_id=capture_ctx.empresa_id,
            device_id=capture_ctx.device_id,
            content_type=content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if capture_ctx.device_id:
        device = await db.get(Dispositivo, capture_ctx.device_id)
        if device:
            await device_service.touch_last_used(db, device)
            await db.commit()

    return CaptureInvoiceResponse(
        invoice=invoice_to_response(invoice),
        processed_image_url=None,
        preprocess_skipped=False,
        extraction_summary=ExtractionSummary(),
    )


@router.get("", response_model=PaginatedInvoicesResponse)
async def list_invoices(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    uf: str | None = None,
    emitter_cnpj: str | None = None,
    status: InvoiceStatus | None = None,
    sort_by: str = Query(default="created_at", pattern="^(created_at|issued_at|status)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db_session),
) -> PaginatedInvoicesResponse:
    invoices, total = await invoice_service.list_invoices(
        db=db,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        created_from=created_from,
        created_to=created_to,
        uf=uf,
        emitter_cnpj=emitter_cnpj,
        status=status,
        empresa_id=auth.empresa_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedInvoicesResponse(
        data=[invoice_to_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


MAX_STATUS_IDS = 20


def _parse_status_ids(ids: str) -> list[UUID]:
    parts = [part.strip() for part in ids.split(",") if part.strip()]
    if not parts:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ids is required")
    if len(parts) > MAX_STATUS_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ids accepts at most {MAX_STATUS_IDS} values",
        )
    try:
        return [UUID(part) for part in parts]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ids must be UUIDs",
        ) from exc


@router.get("/statuses", response_model=InvoiceStatusesResponse)
async def list_invoice_statuses(
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    ids: Annotated[str, Query(min_length=1)],
    db: AsyncSession = Depends(get_db_session),
) -> InvoiceStatusesResponse:
    invoice_ids = _parse_status_ids(ids)
    data = await invoice_service.list_statuses(db, invoice_ids, empresa_id=auth.empresa_id)
    return InvoiceStatusesResponse(data=data)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    db: AsyncSession = Depends(get_db_session),
) -> InvoiceResponse:
    invoice = await invoice_service.get_by_id(db, invoice_id, empresa_id=auth.empresa_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice_to_response(invoice)


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    payload: UpdateInvoiceRequest,
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    db: AsyncSession = Depends(get_db_session),
) -> InvoiceResponse:
    invoice = await invoice_service.update_invoice(
        db,
        invoice_id,
        auth.empresa_id,
        issued_at=payload.issued_at,
        total_amount=payload.total_amount,
        discount_amount=payload.discount_amount,
        emitter_name=payload.emitter_name,
    )
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice_to_response(invoice)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: UUID,
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    db: AsyncSession = Depends(get_db_session),
) -> None:
    deleted = await invoice_service.delete_invoice(db, invoice_id, empresa_id=auth.empresa_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.patch("/{invoice_id}/items/{item_id}", response_model=InvoiceItemResponse)
async def update_invoice_item(
    invoice_id: UUID,
    item_id: UUID,
    payload: UpdateInvoiceItemRequest,
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    db: AsyncSession = Depends(get_db_session),
) -> InvoiceItemResponse:
    try:
        item = await invoice_service.update_invoice_item(
            db,
            invoice_id,
            item_id,
            auth.empresa_id,
            description=payload.description,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            total_price=payload.total_price,
            unit=payload.unit,
            category_id=payload.category_id,
            category_id_set="category_id" in payload.model_fields_set,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    invoice = await invoice_service.get_by_id(db, invoice_id, empresa_id=auth.empresa_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    response = invoice_to_response(invoice)
    updated = next((i for i in response.items if i.id == item_id), None)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return updated


@router.delete("/{invoice_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice_item(
    invoice_id: UUID,
    item_id: UUID,
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    db: AsyncSession = Depends(get_db_session),
) -> None:
    deleted = await invoice_service.delete_invoice_item(
        db, invoice_id, item_id, empresa_id=auth.empresa_id
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
