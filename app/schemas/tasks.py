from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class ProcessInvoiceTask(BaseModel):
    invoice_id: UUID


class SendEmailTask(BaseModel):
    type: Literal["magic_link", "invite", "interest"]
    email: EmailStr | None = None
    convite_id: UUID | None = None
    nome: str | None = None
    mensagem: str | None = None
