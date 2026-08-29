from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_gestor_or_operador
from app.schemas.auth import AuthContext
from app.schemas.invoice import decimal_to_str
from app.schemas.search import SemanticSearchRequest, SemanticSearchResponse, SemanticSearchResult
from app.services.encode_client import encode_one

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    payload: SemanticSearchRequest,
    auth: Annotated[AuthContext, Depends(require_gestor_or_operador)],
    db: AsyncSession = Depends(get_db_session),
) -> SemanticSearchResponse:
    query_vector = await encode_one(payload.query)
    if not query_vector:
        return SemanticSearchResponse(results=[])

    filters = ["ii.embedding IS NOT NULL", "inv.status = 'parsed'", "inv.empresa_id = :empresa_id"]
    params: dict = {
        "query_vector": str(query_vector),
        "limit": payload.limit,
        "empresa_id": str(auth.empresa_id),
    }

    if payload.date_from:
        filters.append("inv.issued_at >= :date_from")
        params["date_from"] = payload.date_from
    if payload.date_to:
        filters.append("inv.issued_at <= :date_to")
        params["date_to"] = payload.date_to

    where_clause = " AND ".join(filters)
    sql = text(
        f"""
        SELECT ii.id AS item_id,
               inv.id AS invoice_id,
               ii.description,
               ii.total_price,
               1 - (ii.embedding <=> CAST(:query_vector AS vector)) AS similarity,
               inv.issued_at,
               COALESCE(e.trade_name, e.legal_name) AS emitter_name
        FROM invoice_items ii
        JOIN invoices inv ON inv.id = ii.invoice_id
        LEFT JOIN emitters e ON e.id = inv.emitter_id
        WHERE {where_clause}
        ORDER BY ii.embedding <=> CAST(:query_vector AS vector)
        LIMIT :limit
        """
    )

    result = await db.execute(sql, params)
    results = [
        SemanticSearchResult(
            item_id=row.item_id,
            invoice_id=row.invoice_id,
            description=row.description,
            total_price=decimal_to_str(row.total_price),
            similarity=float(row.similarity),
            issued_at=row.issued_at,
            emitter_name=row.emitter_name,
        )
        for row in result
    ]
    return SemanticSearchResponse(results=results)
