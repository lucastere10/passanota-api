import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field



class InviteCreateRequest(BaseModel):
    email: EmailStr


class InviteResponse(BaseModel):
    id: uuid.UUID
    email: str
    empresa_id: uuid.UUID
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class OperadorInviteRequest(BaseModel):
    email: EmailStr


class FuncionarioListItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    nome: str | None
    role: str
    is_active: bool
    created_at: datetime


class FuncionarioUpdateRequest(BaseModel):
    is_active: bool | None = None
    nome: str | None = Field(default=None, max_length=255)
