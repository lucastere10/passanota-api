from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_gestor_or_operador
from app.models import Category
from app.schemas.auth import AuthContext
from app.schemas.category import CategoryListResponse, CategoryResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
async def list_categories(
    _auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    db: AsyncSession = Depends(get_db_session),
) -> CategoryListResponse:
    result = await db.execute(select(Category).order_by(Category.name))
    categories = result.scalars().all()
    return CategoryListResponse(
        data=[CategoryResponse.model_validate(cat) for cat in categories]
    )
