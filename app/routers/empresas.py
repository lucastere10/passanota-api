import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_auth_context, get_current_user, get_db_session, require_gestor
from app.integrations.resend import ResendError
from app.models import ConviteRole, Empresa, Funcionario
from app.schemas.auth import AuthContext, AuthUser
from app.schemas.auth_api import EmpresaMembership
from app.schemas.device import EmpresaPinStatusResponse, EmpresaPinUpdateRequest
from app.schemas.invite import (
    FuncionarioListItem,
    FuncionarioUpdateRequest,
    InviteResponse,
    OperadorInviteRequest,
)
from app.services.device_service import device_service
from app.services.invite_service import invite_service

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("/mine", response_model=list[EmpresaMembership])
async def list_my_empresas(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session),
) -> list[EmpresaMembership]:
    result = await db.execute(
        select(Funcionario, Empresa)
        .join(Empresa, Empresa.id == Funcionario.empresa_id)
        .where(Funcionario.user_id == user.id, Funcionario.is_active.is_(True))
    )
    return [
        EmpresaMembership(
            id=empresa.id,
            nome=empresa.nome,
            role=funcionario.role.value,
            funcionario_id=funcionario.id,
            funcionario_nome=funcionario.nome,
        )
        for funcionario, empresa in result.all()
    ]


@router.post("/{empresa_id}/convites", response_model=InviteResponse)
async def invite_operador(
    empresa_id: uuid.UUID,
    payload: OperadorInviteRequest,
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> InviteResponse:
    if auth.empresa_id != empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa não autorizada")

    convite, _token = await invite_service.create_invite(
        db,
        email=payload.email,
        empresa_id=empresa_id,
        role=ConviteRole.OPERADOR,
        invited_by_user_id=auth.user.id,
    )

    try:
        await invite_service.send_invite_email_for_convite(db, convite)
    except (ResendError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Falha ao enviar convite: {exc}",
        ) from exc

    await db.commit()
    await db.refresh(convite)
    return InviteResponse(
        id=convite.id,
        email=convite.email,
        empresa_id=convite.empresa_id,
        role=convite.role.value,
        expires_at=convite.expires_at,
        accepted_at=convite.accepted_at,
        created_at=convite.created_at,
    )


@router.get("/{empresa_id}/funcionarios", response_model=list[FuncionarioListItem])
async def list_funcionarios(
    empresa_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> list[FuncionarioListItem]:
    if auth.empresa_id != empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa não autorizada")

    result = await db.execute(
        select(Funcionario)
        .where(Funcionario.empresa_id == empresa_id)
        .order_by(Funcionario.created_at.desc())
    )
    return [
        FuncionarioListItem(
            id=f.id,
            user_id=f.user_id,
            nome=f.nome,
            role=f.role.value,
            is_active=f.is_active,
            created_at=f.created_at,
        )
        for f in result.scalars().all()
    ]


@router.patch("/{empresa_id}/funcionarios/{funcionario_id}", response_model=FuncionarioListItem)
async def update_funcionario(
    empresa_id: uuid.UUID,
    funcionario_id: uuid.UUID,
    payload: FuncionarioUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> FuncionarioListItem:
    if auth.empresa_id != empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa não autorizada")

    funcionario = await db.get(Funcionario, funcionario_id)
    if not funcionario or funcionario.empresa_id != empresa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado")

    if funcionario.id == auth.funcionario.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível desativar a si mesmo")

    if payload.is_active is not None:
        funcionario.is_active = payload.is_active
    if payload.nome is not None:
        funcionario.nome = payload.nome

    await db.commit()
    await db.refresh(funcionario)
    return FuncionarioListItem(
        id=funcionario.id,
        user_id=funcionario.user_id,
        nome=funcionario.nome,
        role=funcionario.role.value,
        is_active=funcionario.is_active,
        created_at=funcionario.created_at,
    )


@router.get("/{empresa_id}/pin", response_model=EmpresaPinStatusResponse)
async def get_empresa_pin_status(
    empresa_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(require_gestor)],
) -> EmpresaPinStatusResponse:
    if auth.empresa_id != empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa não autorizada")
    return EmpresaPinStatusResponse(pin_configured=await device_service.is_pin_configured(auth.empresa))


@router.patch("/{empresa_id}/pin", response_model=EmpresaPinStatusResponse)
async def update_empresa_pin(
    empresa_id: uuid.UUID,
    payload: EmpresaPinUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_gestor)],
    db: AsyncSession = Depends(get_db_session),
) -> EmpresaPinStatusResponse:
    if auth.empresa_id != empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Empresa não autorizada")

    await device_service.set_empresa_pin(db, auth.empresa, payload.pin)
    return EmpresaPinStatusResponse(pin_configured=True)
