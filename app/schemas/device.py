import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmpresaPinStatusResponse(BaseModel):
    pin_configured: bool


class EmpresaPinUpdateRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=20)


class PairingSessionResponse(BaseModel):
    token: str
    expires_at: datetime
    pairing_url: str


class DevicePairRequest(BaseModel):
    pairing_token: str = Field(min_length=1)
    pin: str = Field(min_length=4, max_length=20)
    nome: str | None = Field(default=None, max_length=255)


class DevicePairResponse(BaseModel):
    device_token: str
    device_id: uuid.UUID
    empresa_nome: str


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID
    nome: str | None
    is_active: bool
    last_used_at: datetime | None
    user_agent: str | None
    created_at: datetime
    invoice_count: int = 0


class DeviceUpdateRequest(BaseModel):
    nome: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class DeviceMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID
    empresa_nome: str
    nome: str | None
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
