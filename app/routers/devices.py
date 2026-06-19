import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db_session,
    get_device_context,
    require_gestor,
)
from app.models import Empresa, InvoiceStatus
from app.schemas.auth import AuthContext, DeviceContext
from app.schemas.device import (
    DeviceMeResponse,
    DevicePairRequest,
    DevicePairResponse,
    DeviceResponse,
    DeviceUpdateRequest,
    PairingSessionResponse,
)
from app.schemas.invoice import PaginatedInvoicesResponse, invoice_to_response
from app.services.device_service import DeviceServiceError, device_service
from app.services.invoice_service import invoice_service

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/pairing-sessions", response_model=PairingSessionResponse)
async def create_pairing_session(
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> PairingSessionResponse:
    if not await device_service.is_pin_configured(auth.empresa):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure o PIN da empresa antes de conectar dispositivos",
        )

    try:
        session, token = await device_service.create_pairing_session(
            db,
            empresa_id=auth.empresa_id,
            created_by_user_id=auth.user.id,
        )
    except DeviceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await db.commit()
    return PairingSessionResponse(
        token=token,
        expires_at=session.expires_at,
        pairing_url=device_service.build_pairing_url(token),
    )


@router.post("/pair", response_model=DevicePairResponse)
async def pair_device(
    payload: DevicePairRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> DevicePairResponse:
    user_agent = request.headers.get("User-Agent")
    try:
        dispositivo, device_token = await device_service.pair_device(
            db,
            pairing_token=payload.pairing_token,
            pin=payload.pin,
            nome=payload.nome,
            user_agent=user_agent,
        )
    except DeviceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    empresa = await db.get(Empresa, dispositivo.empresa_id)
    return DevicePairResponse(
        device_token=device_token,
        device_id=dispositivo.id,
        empresa_nome=empresa.nome if empresa else "",
    )


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> list[DeviceResponse]:
    rows = await device_service.list_devices(db, auth.empresa_id)
    return [
        DeviceResponse(
            id=device.id,
            empresa_id=device.empresa_id,
            nome=device.nome,
            is_active=device.is_active,
            last_used_at=device.last_used_at,
            user_agent=device.user_agent,
            created_at=device.created_at,
            invoice_count=count,
        )
        for device, count in rows
    ]


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: uuid.UUID,
    payload: DeviceUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> DeviceResponse:
    dispositivo = await device_service.get_device(db, device_id, auth.empresa_id)
    if not dispositivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo não encontrado")

    dispositivo = await device_service.update_device(
        db,
        dispositivo,
        nome=payload.nome,
        is_active=payload.is_active,
    )
    rows = await device_service.list_devices(db, auth.empresa_id)
    count = next((c for d, c in rows if d.id == dispositivo.id), 0)
    return DeviceResponse(
        id=dispositivo.id,
        empresa_id=dispositivo.empresa_id,
        nome=dispositivo.nome,
        is_active=dispositivo.is_active,
        last_used_at=dispositivo.last_used_at,
        user_agent=dispositivo.user_agent,
        created_at=dispositivo.created_at,
        invoice_count=count,
    )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> None:
    dispositivo = await device_service.get_device(db, device_id, auth.empresa_id)
    if not dispositivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo não encontrado")
    await device_service.revoke_device(db, dispositivo)


@router.get("/me", response_model=DeviceMeResponse)
async def get_device_me(
    device_ctx: Annotated[DeviceContext, Depends(get_device_context)],
) -> DeviceMeResponse:
    return DeviceMeResponse(
        id=device_ctx.device.id,
        empresa_id=device_ctx.empresa_id,
        empresa_nome=device_ctx.empresa.nome,
        nome=device_ctx.device.nome,
        is_active=device_ctx.device.is_active,
        last_used_at=device_ctx.device.last_used_at,
        created_at=device_ctx.device.created_at,
    )


@router.get("/me/invoices", response_model=PaginatedInvoicesResponse)
async def list_device_invoices(
    device_ctx: Annotated[DeviceContext, Depends(get_device_context)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: InvoiceStatus | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> PaginatedInvoicesResponse:
    invoices, total = await invoice_service.list_invoices(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        empresa_id=device_ctx.empresa_id,
        device_id=device_ctx.device_id,
    )
    return PaginatedInvoicesResponse(
        data=[invoice_to_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )
