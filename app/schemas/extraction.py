from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

VALID_CATEGORY_SLUGS = frozenset(
    {"alimentacao", "bebidas", "higiene", "limpeza", "vestuario", "outros"}
)


class ExtractedItem(BaseModel):
    descricao: str = Field(..., min_length=1)
    valor: Decimal = Field(..., ge=0)
    quantidade: Decimal | None = Field(default=None, ge=0)
    categoria: str | None = None

    @field_validator("descricao")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("categoria")
    @classmethod
    def normalize_categoria(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = value.strip().lower().replace(" ", "_")
        if slug in VALID_CATEGORY_SLUGS:
            return slug
        return None


class ExtractedInvoice(BaseModel):
    fornecedor: str | None = None
    cnpj: str | None = None
    data: str | None = None
    itens: list[ExtractedItem] = Field(default_factory=list)
    total: Decimal | None = Field(default=None, ge=0)
    confianca: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("fornecedor")
    @classmethod
    def strip_fornecedor(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("cnpj")
    @classmethod
    def normalize_cnpj(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = "".join(c for c in value if c.isdigit())
        return digits if len(digits) == 14 else None


@dataclass(frozen=True, slots=True)
class VisionExtractionResult:
    invoice: ExtractedInvoice
    raw_response: dict
    model: str
