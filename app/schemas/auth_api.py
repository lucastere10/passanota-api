import uuid

from pydantic import BaseModel, EmailStr, Field


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    message: str = "Se o e-mail estiver cadastrado, você receberá um link de acesso em breve."


class CompleteProfileRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=255)


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str | None
    nome: str | None


class EmpresaMembership(BaseModel):
    id: uuid.UUID
    nome: str
    role: str
    funcionario_id: uuid.UUID
    funcionario_nome: str | None = None


class PendingInvite(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    empresa_nome: str
    role: str


class AuthMeResponse(BaseModel):
    user: UserProfile
    is_platform_admin: bool
    empresas: list[EmpresaMembership]
    pending_invite: PendingInvite | None
    profile_complete: bool
