import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import FuncionarioRole


class EmpresaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    cnpj: str | None = Field(default=None, min_length=14, max_length=14)
    pin: str | None = Field(default=None, max_length=20)


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
    cnpj: str | None = Field(default=None, min_length=14, max_length=14)
    pin: str | None = Field(default=None, max_length=20)


class EmpresaResponse(EmpresaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class FuncionarioBase(BaseModel):
    role: FuncionarioRole
    nome: str | None = Field(default=None, max_length=255)


class FuncionarioCreate(FuncionarioBase):
    user_id: uuid.UUID


class FuncionarioUpdate(BaseModel):
    role: FuncionarioRole | None = None
    nome: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class FuncionarioResponse(FuncionarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
