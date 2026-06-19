from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db_session
from app.integrations.resend import ResendError
from app.integrations.supabase import SupabaseAuthError, SupabaseConfigError
from app.schemas.auth import AuthUser
from app.schemas.auth_api import (
    AuthMeResponse,
    CompleteProfileRequest,
    MagicLinkRequest,
    MagicLinkResponse,
)
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/magic-link", response_model=MagicLinkResponse)
async def send_magic_link(
    payload: MagicLinkRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MagicLinkResponse:
    try:
        await auth_service.send_magic_link(db, payload.email)
        await db.commit()
    except (ResendError, SupabaseConfigError, SupabaseAuthError):
        pass
    return MagicLinkResponse()


@router.get("/me", response_model=AuthMeResponse)
async def get_me(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session),
) -> AuthMeResponse:
    response = await auth_service.get_me(db, user.id, user.email)
    await db.commit()
    return response


@router.post("/complete-profile", response_model=AuthMeResponse)
async def complete_profile(
    payload: CompleteProfileRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session),
) -> AuthMeResponse:
    try:
        return await auth_service.complete_profile(db, user.id, user.email, payload.nome)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
