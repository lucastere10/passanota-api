import uuid

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.integrations.supabase import SupabaseAuthError, SupabaseConfigError, verify_access_token
from app.models import Empresa, Funcionario, FuncionarioRole, PlatformAdmin
from app.schemas.auth import AuthContext, AuthUser, CaptureContext, DeviceContext

from app.services.device_service import device_service


def resolve_supabase_authorization(
    authorization: str | None,
    x_supabase_authorization: str | None = None,
) -> str | None:
    """Supabase JWT: custom header when Cloud Run IAM uses Authorization."""
    if x_supabase_authorization:
        return x_supabase_authorization
    return authorization


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_supabase_authorization: str | None = Header(default=None, alias="X-Supabase-Authorization"),
) -> AuthUser:
    auth_header = resolve_supabase_authorization(authorization, x_supabase_authorization)
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        user_data = await verify_access_token(token)
    except SupabaseConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user_id_raw = user_data.get("id")
    if not user_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = uuid.UUID(str(user_id_raw))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id in token",
        ) from exc

    return AuthUser(id=user_id, email=user_data.get("email"))


async def get_platform_admin(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlatformAdmin:
    result = await db.execute(select(PlatformAdmin).where(PlatformAdmin.user_id == user.id))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return admin


require_platform_admin = get_platform_admin


async def get_auth_context(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_empresa_id: str | None = Header(default=None, alias="X-Empresa-Id"),
) -> AuthContext:
    if not x_empresa_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Empresa-Id header",
        )

    try:
        empresa_id = uuid.UUID(x_empresa_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Empresa-Id header",
        ) from exc

    result = await db.execute(
        select(Funcionario, Empresa)
        .join(Empresa, Empresa.id == Funcionario.empresa_id)
        .where(
            Funcionario.user_id == user.id,
            Funcionario.empresa_id == empresa_id,
            Funcionario.is_active.is_(True),
            Empresa.is_active.is_(True),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an active member of this empresa",
        )

    funcionario, empresa = row
    return AuthContext(user=user, funcionario=funcionario, empresa=empresa)


def require_roles(*roles: FuncionarioRole) -> Callable[..., AuthContext]:
    allowed = frozenset(roles)

    async def _require_roles(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        if auth.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return auth

    return _require_roles


require_gestor = require_roles(FuncionarioRole.GESTOR)
require_gestor_or_operador = require_roles(FuncionarioRole.GESTOR, FuncionarioRole.OPERADOR)


async def get_device_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
) -> DeviceContext:
    if not x_device_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device token",
        )

    row = await device_service.get_device_by_token(db, x_device_token.strip())
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked device token",
        )

    device, empresa = row
    return DeviceContext(device=device, empresa=empresa)


async def get_capture_context(
    authorization: str | None = Header(default=None),
    x_supabase_authorization: str | None = Header(default=None, alias="X-Supabase-Authorization"),
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
    x_empresa_id: str | None = Header(default=None, alias="X-Empresa-Id"),
    db: AsyncSession = Depends(get_db),
) -> CaptureContext:
    if x_device_token:
        row = await device_service.get_device_by_token(db, x_device_token.strip())
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked device token",
            )
        device, empresa = row
        return CaptureContext(empresa_id=empresa.id, device_id=device.id)

    auth_header = resolve_supabase_authorization(authorization, x_supabase_authorization)
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication",
        )

    user = await get_current_user(authorization, x_supabase_authorization)
    auth = await get_auth_context(user, db, x_empresa_id)
    if auth.role not in (FuncionarioRole.GESTOR, FuncionarioRole.OPERADOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this action",
        )
    return CaptureContext(empresa_id=auth.empresa_id, device_id=None)


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db
