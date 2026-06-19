from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    limit: int = Field(default=20, ge=1, le=100)
    date_from: datetime | None = None
    date_to: datetime | None = None


class SemanticSearchResult(BaseModel):
    item_id: UUID
    invoice_id: UUID
    description: str
    total_price: str | None
    similarity: float
    issued_at: datetime | None
    emitter_name: str | None


class SemanticSearchResponse(BaseModel):
    results: list[SemanticSearchResult]
