import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AdminEmpresaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    cnpj: str | None = Field(default=None, min_length=14, max_length=14)
    gestor_email: EmailStr


class AdminEmpresaListItem(BaseModel):
    id: uuid.UUID
    nome: str
    cnpj: str | None
    is_active: bool
    created_at: datetime
    gestor_email: str | None = None
    gestor_nome: str | None = None
    gestor_convite_pendente: bool = False
    invoices_total: int = 0
    invoices_this_month: int = 0
    monthly_invoice_limit: int | None = None
    funcionarios_count: int = 0
    dispositivos_ativos_count: int = 0


class AdminEmpresaDetail(AdminEmpresaListItem):
    updated_at: datetime


class AdminEmpresaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
    cnpj: str | None = Field(default=None, min_length=14, max_length=14)
    is_active: bool | None = None
    monthly_invoice_limit: int | None = None

    @field_validator("monthly_invoice_limit")
    @classmethod
    def validate_limit(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("monthly_invoice_limit must be >= 0")
        return value


class AdminEmpresaResponse(BaseModel):
    id: uuid.UUID
    nome: str
    cnpj: str | None
    is_active: bool
    monthly_invoice_limit: int | None
    created_at: datetime
    updated_at: datetime


class TopEmpresaMonthItem(BaseModel):
    nome: str
    invoices_this_month: int


class AdminPlatformOverview(BaseModel):
    empresas_total: int
    empresas_active: int
    empresas_inactive: int
    invoices_total: int
    invoices_this_month: int
    devices_active: int
    platform_admins: int
    gestores_active: int
    operadores_active: int
    funcionarios_inactive: int
    convites_pendentes_gestor: int
    convites_pendentes_operador: int
    top_empresas_month: list[TopEmpresaMonthItem]


class EmpresaUsageResponse(BaseModel):
    invoices_total: int
    invoices_this_month: int
    monthly_invoice_limit: int | None
    is_unlimited: bool
    usage_percentage: float | None = None


class AdminEmpresaClearDataRequest(BaseModel):
    confirm_nome: str = Field(min_length=1)


class AdminEmpresaClearDataResponse(BaseModel):
    invoices_deleted: int
    funcionarios_deleted: int
    convites_deleted: int
    dispositivos_deleted: int
    pairing_sessions_deleted: int
    storage_objects_deleted: int


class InterestRequest(BaseModel):
    email: EmailStr
    nome: str | None = Field(default=None, max_length=255)
    mensagem: str | None = Field(default=None, max_length=2000)


class InterestResponse(BaseModel):
    message: str = "Obrigado pelo interesse! Entraremos em contato em breve."
