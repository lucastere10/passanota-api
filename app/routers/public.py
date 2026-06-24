from fastapi import APIRouter

from app.schemas.admin import InterestRequest, InterestResponse
from app.services.auth_service import auth_service
router = APIRouter(prefix="/public", tags=["public"])


@router.post("/interesse", response_model=InterestResponse)
async def submit_interest(payload: InterestRequest) -> InterestResponse:
    await auth_service.submit_interest(payload.email, payload.nome, payload.mensagem)
    return InterestResponse()
