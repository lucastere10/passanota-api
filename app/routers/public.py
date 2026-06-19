from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.integrations.resend import ResendError
from app.schemas.admin import InterestRequest, InterestResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/interesse", response_model=InterestResponse)
async def submit_interest(payload: InterestRequest) -> InterestResponse:
    try:
        await auth_service.submit_interest(payload.email, payload.nome, payload.mensagem)
    except ResendError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de e-mail indisponível",
        ) from exc
    return InterestResponse()
