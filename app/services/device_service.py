import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import DevicePairingSession, Dispositivo, Empresa, Invoice

settings = get_settings()

PAIRING_EXPIRY_MINUTES = 10
MAX_PIN_ATTEMPTS = 5


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def _verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())
    except ValueError:
        return False


class DeviceServiceError(Exception):
    pass


class DeviceService:
    async def set_empresa_pin(self, db: AsyncSession, empresa: Empresa, pin: str) -> None:
        empresa.pin = _hash_pin(pin)
        await db.commit()

    async def is_pin_configured(self, empresa: Empresa) -> bool:
        return bool(empresa.pin)

    async def create_pairing_session(
        self,
        db: AsyncSession,
        *,
        empresa_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
    ) -> tuple[DevicePairingSession, str]:
        empresa = await db.get(Empresa, empresa_id)
        if not empresa or not empresa.pin:
            raise DeviceServiceError("PIN da empresa não configurado")

        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        session = DevicePairingSession(
            empresa_id=empresa_id,
            token_hash=_hash_token(token),
            expires_at=now + timedelta(minutes=PAIRING_EXPIRY_MINUTES),
            created_by_user_id=created_by_user_id,
        )
        db.add(session)
        await db.flush()
        return session, token

    def build_pairing_url(self, token: str) -> str:
        base = settings.frontend_url.rstrip("/")
        return f"{base}/m/pair?token={token}"

    async def pair_device(
        self,
        db: AsyncSession,
        *,
        pairing_token: str,
        pin: str,
        nome: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Dispositivo, str]:
        now = datetime.now(timezone.utc)
        token_hash = _hash_token(pairing_token)

        result = await db.execute(
            select(DevicePairingSession)
            .options(selectinload(DevicePairingSession.empresa))
            .where(DevicePairingSession.token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise DeviceServiceError("Sessão de pareamento inválida")
        if session.used_at is not None:
            raise DeviceServiceError("Sessão de pareamento já utilizada")
        if session.expires_at < now:
            raise DeviceServiceError("Sessão de pareamento expirada")
        if session.pin_attempts >= MAX_PIN_ATTEMPTS:
            raise DeviceServiceError("Sessão de pareamento bloqueada")

        empresa = session.empresa
        if not empresa or not empresa.pin:
            raise DeviceServiceError("PIN da empresa não configurado")

        if not _verify_pin(pin, empresa.pin):
            session.pin_attempts += 1
            await db.commit()
            remaining = MAX_PIN_ATTEMPTS - session.pin_attempts
            if remaining <= 0:
                raise DeviceServiceError("Sessão de pareamento bloqueada por tentativas inválidas")
            raise DeviceServiceError(f"PIN incorreto. {remaining} tentativa(s) restante(s).")

        session.used_at = now
        device_token = secrets.token_urlsafe(32)
        dispositivo = Dispositivo(
            empresa_id=session.empresa_id,
            nome=nome.strip() if nome else None,
            token_hash=_hash_token(device_token),
            paired_by_user_id=session.created_by_user_id,
            user_agent=user_agent[:512] if user_agent else None,
        )
        db.add(dispositivo)
        await db.commit()
        await db.refresh(dispositivo)
        return dispositivo, device_token

    async def get_device_by_token(
        self, db: AsyncSession, device_token: str
    ) -> tuple[Dispositivo, Empresa] | None:
        token_hash = _hash_token(device_token)
        result = await db.execute(
            select(Dispositivo, Empresa)
            .join(Empresa, Empresa.id == Dispositivo.empresa_id)
            .where(Dispositivo.token_hash == token_hash, Dispositivo.is_active.is_(True), Empresa.is_active.is_(True))
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def touch_last_used(self, db: AsyncSession, dispositivo: Dispositivo) -> None:
        dispositivo.last_used_at = datetime.now(timezone.utc)
        await db.commit()

    async def list_devices(self, db: AsyncSession, empresa_id: uuid.UUID) -> list[tuple[Dispositivo, int]]:
        invoice_counts = (
            select(Invoice.device_id, func.count().label("invoice_count"))
            .where(Invoice.device_id.is_not(None), Invoice.empresa_id == empresa_id)
            .group_by(Invoice.device_id)
            .subquery()
        )
        result = await db.execute(
            select(Dispositivo, func.coalesce(invoice_counts.c.invoice_count, 0))
            .outerjoin(invoice_counts, Dispositivo.id == invoice_counts.c.device_id)
            .where(Dispositivo.empresa_id == empresa_id)
            .order_by(Dispositivo.created_at.desc())
        )
        return [(row[0], int(row[1])) for row in result.all()]

    async def get_device(
        self, db: AsyncSession, device_id: uuid.UUID, empresa_id: uuid.UUID
    ) -> Dispositivo | None:
        result = await db.execute(
            select(Dispositivo).where(
                Dispositivo.id == device_id,
                Dispositivo.empresa_id == empresa_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_device(
        self,
        db: AsyncSession,
        dispositivo: Dispositivo,
        *,
        nome: str | None = None,
        is_active: bool | None = None,
    ) -> Dispositivo:
        if nome is not None:
            dispositivo.nome = nome.strip() or None
        if is_active is not None:
            dispositivo.is_active = is_active
        await db.commit()
        await db.refresh(dispositivo)
        return dispositivo

    async def revoke_device(self, db: AsyncSession, dispositivo: Dispositivo) -> None:
        dispositivo.is_active = False
        await db.commit()


device_service = DeviceService()
