import uuid
from dataclasses import dataclass

from app.models import Dispositivo, Empresa, Funcionario, FuncionarioRole


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: uuid.UUID
    email: str | None


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: AuthUser
    funcionario: Funcionario
    empresa: Empresa

    @property
    def role(self) -> FuncionarioRole:
        return self.funcionario.role

    @property
    def empresa_id(self) -> uuid.UUID:
        return self.empresa.id

    def is_gestor(self) -> bool:
        return self.role == FuncionarioRole.GESTOR

    def is_operador(self) -> bool:
        return self.role == FuncionarioRole.OPERADOR


@dataclass(frozen=True, slots=True)
class DeviceContext:
    device: Dispositivo
    empresa: Empresa

    @property
    def device_id(self) -> uuid.UUID:
        return self.device.id

    @property
    def empresa_id(self) -> uuid.UUID:
        return self.empresa.id


@dataclass(frozen=True, slots=True)
class CaptureContext:
    empresa_id: uuid.UUID
    device_id: uuid.UUID | None = None
