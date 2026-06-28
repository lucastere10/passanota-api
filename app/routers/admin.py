import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_platform_admin
from app.models import ConviteRole, Empresa, PlatformAdmin
from app.schemas.admin import (
    AdminEmpresaClearDataRequest,
    AdminEmpresaClearDataResponse,
    AdminEmpresaCreate,
    AdminEmpresaDetail,
    AdminEmpresaListItem,
    AdminEmpresaResponse,
    AdminEmpresaUpdate,
    AdminPlatformOverview,
)
from app.schemas.invite import InviteResponse, OperadorInviteRequest
from app.schemas.tasks import SendEmailTask
from app.services.admin_service import (
    DEFAULT_MONTHLY_INVOICE_LIMIT,
    EmpresaClearDataError,
    EmpresaNotFoundError,
    admin_service,
)
from app.services.invite_service import invite_service
from app.services.task_dispatcher import dispatch_email_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminPlatformOverview)
async def get_overview(
    _admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> AdminPlatformOverview:
    data = await admin_service.get_platform_overview(db)
    return AdminPlatformOverview(**data)


@router.get("/empresas", response_model=list[AdminEmpresaListItem])
async def list_empresas(
    _admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> list[AdminEmpresaListItem]:
    result = await db.execute(select(Empresa).order_by(Empresa.created_at.desc()))
    empresas = result.scalars().all()
    now = datetime.now(timezone.utc)

    items: list[AdminEmpresaListItem] = []
    for empresa in empresas:
        item_data = await admin_service.build_empresa_list_item(db, empresa, now)
        items.append(AdminEmpresaListItem(**item_data))
    return items


@router.get("/empresas/{empresa_id}", response_model=AdminEmpresaDetail)
async def get_empresa(
    empresa_id: uuid.UUID,
    _admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> AdminEmpresaDetail:
    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")

    item_data = await admin_service.build_empresa_list_item(db, empresa)
    return AdminEmpresaDetail(**item_data, updated_at=empresa.updated_at)


@router.patch("/empresas/{empresa_id}", response_model=AdminEmpresaDetail)
async def update_empresa(
    empresa_id: uuid.UUID,
    payload: AdminEmpresaUpdate,
    _admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> AdminEmpresaDetail:
    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")

    if payload.nome is not None:
        empresa.nome = payload.nome
    if payload.cnpj is not None:
        empresa.cnpj = payload.cnpj or None
    if payload.is_active is not None:
        was_active = empresa.is_active
        empresa.is_active = payload.is_active
        if was_active and not payload.is_active:
            await admin_service.revoke_empresa_devices(db, empresa.id)
    if "monthly_invoice_limit" in payload.model_fields_set:
        empresa.monthly_invoice_limit = payload.monthly_invoice_limit

    await db.commit()
    await db.refresh(empresa)

    item_data = await admin_service.build_empresa_list_item(db, empresa)
    return AdminEmpresaDetail(**item_data, updated_at=empresa.updated_at)


@router.post("/empresas", response_model=AdminEmpresaResponse, status_code=status.HTTP_201_CREATED)
async def create_empresa(
    payload: AdminEmpresaCreate,
    admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> AdminEmpresaResponse:
    empresa = Empresa(
        nome=payload.nome,
        cnpj=payload.cnpj,
        is_active=True,
        monthly_invoice_limit=DEFAULT_MONTHLY_INVOICE_LIMIT,
    )
    db.add(empresa)
    await db.flush()

    convite, _token = await invite_service.create_invite(
        db,
        email=payload.gestor_email,
        empresa_id=empresa.id,
        role=ConviteRole.GESTOR,
        invited_by_user_id=admin.user_id,
    )

    await db.commit()
    await db.refresh(empresa)
    await dispatch_email_task(SendEmailTask(type="invite", convite_id=convite.id))
    return AdminEmpresaResponse(
        id=empresa.id,
        nome=empresa.nome,
        cnpj=empresa.cnpj,
        is_active=empresa.is_active,
        monthly_invoice_limit=empresa.monthly_invoice_limit,
        created_at=empresa.created_at,
        updated_at=empresa.updated_at,
    )


@router.post("/empresas/{empresa_id}/convites", response_model=InviteResponse)
async def resend_gestor_invite(
    empresa_id: uuid.UUID,
    payload: OperadorInviteRequest,
    admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> InviteResponse:
    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")

    convite, _token = await invite_service.create_invite(
        db,
        email=payload.email,
        empresa_id=empresa.id,
        role=ConviteRole.GESTOR,
        invited_by_user_id=admin.user_id,
    )

    await db.commit()
    await db.refresh(convite)
    await dispatch_email_task(SendEmailTask(type="invite", convite_id=convite.id))
    return InviteResponse(
        id=convite.id,
        email=convite.email,
        empresa_id=convite.empresa_id,
        role=convite.role.value,
        expires_at=convite.expires_at,
        accepted_at=convite.accepted_at,
        created_at=convite.created_at,
    )


@router.post(
    "/empresas/{empresa_id}/clear-data",
    response_model=AdminEmpresaClearDataResponse,
)
async def clear_empresa_data(
    empresa_id: uuid.UUID,
    payload: AdminEmpresaClearDataRequest,
    admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> AdminEmpresaClearDataResponse:
    try:
        result = await admin_service.clear_empresa_data(
            db,
            empresa_id,
            confirm_nome=payload.confirm_nome,
        )
    except EmpresaNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    except EmpresaClearDataError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    logger.warning(
        "admin_clear_empresa_data",
        extra={
            "admin_user_id": str(admin.user_id),
            "empresa_id": str(empresa_id),
            **result,
        },
    )
    return AdminEmpresaClearDataResponse(**result)
