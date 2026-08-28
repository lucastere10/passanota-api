from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ProcessInvoiceTask(BaseModel):
    invoice_id: UUID


class SendEmailTask(BaseModel):
    type: Literal["magic_link", "invite", "interest"]
    email: EmailStr | None = None
    convite_id: UUID | None = None
    nome: str | None = None
    mensagem: str | None = None


class EncodeRequest(BaseModel):
    texts: list[str] = Field(default_factory=list, max_length=256)


class EncodeResponse(BaseModel):
    vectors: list[list[float]]
