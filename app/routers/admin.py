import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_platform_admin
from app.models import Convite, ConviteRole, Empresa, PlatformAdmin
from app.schemas.admin import AdminEmpresaCreate, AdminEmpresaListItem, AdminEmpresaResponse
from app.schemas.invite import InviteResponse, OperadorInviteRequest
from app.schemas.tasks import SendEmailTask
from app.services.invite_service import invite_service
from app.services.task_dispatcher import dispatch_email_task

router = APIRouter(prefix="/admin", tags=["admin"])


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
        convite_result = await db.execute(
            select(Convite.id).where(
                Convite.empresa_id == empresa.id,
                Convite.role == ConviteRole.GESTOR,
                Convite.accepted_at.is_(None),
                Convite.expires_at > now,
            ).limit(1)
        )
        items.append(
            AdminEmpresaListItem(
                id=empresa.id,
                nome=empresa.nome,
                cnpj=empresa.cnpj,
                created_at=empresa.created_at,
                gestor_convite_pendente=convite_result.scalar_one_or_none() is not None,
            )
        )
    return items


@router.post("/empresas", response_model=AdminEmpresaResponse, status_code=status.HTTP_201_CREATED)
async def create_empresa(
    payload: AdminEmpresaCreate,
    admin: Annotated[PlatformAdmin, Depends(require_platform_admin)],
    db: AsyncSession = Depends(get_db_session),
) -> AdminEmpresaResponse:
    empresa = Empresa(nome=payload.nome, cnpj=payload.cnpj)
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
