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
    InvoiceResponse,
    PaginatedInvoicesResponse,
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
    uf: str | None = None,
    emitter_cnpj: str | None = None,
    status: InvoiceStatus | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> PaginatedInvoicesResponse:
    invoices, total = await invoice_service.list_invoices(
        db=db,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        uf=uf,
        emitter_cnpj=emitter_cnpj,
        status=status,
        empresa_id=auth.empresa_id,
    )
    return PaginatedInvoicesResponse(
        data=[invoice_to_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


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
