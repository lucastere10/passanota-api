import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AdminEmpresaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    cnpj: str | None = Field(default=None, min_length=14, max_length=14)
    gestor_email: EmailStr


class AdminEmpresaListItem(BaseModel):
    id: uuid.UUID
    nome: str
    cnpj: str | None
    created_at: datetime
    gestor_convite_pendente: bool = False


class AdminEmpresaResponse(BaseModel):
    id: uuid.UUID
    nome: str
    cnpj: str | None
    created_at: datetime
    updated_at: datetime


class InterestRequest(BaseModel):
    email: EmailStr
    nome: str | None = Field(default=None, max_length=255)
    mensagem: str | None = Field(default=None, max_length=2000)


class InterestResponse(BaseModel):
    message: str = "Obrigado pelo interesse! Entraremos em contato em breve."
