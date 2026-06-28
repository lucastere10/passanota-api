import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.supabase import generate_magic_link
from app.models import Convite, ConviteRole, Empresa, Funcionario, FuncionarioRole
from app.services.email_service import send_invite_email

INVITE_EXPIRY_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class InviteService:
    async def create_invite(
        self,
        db: AsyncSession,
        *,
        email: str,
        empresa_id: uuid.UUID,
        role: ConviteRole,
        invited_by_user_id: uuid.UUID | None = None,
    ) -> tuple[Convite, str]:
        normalized = _normalize_email(email)
        now = datetime.now(timezone.utc)

        existing = await db.execute(
            select(Convite).where(
                Convite.email == normalized,
                Convite.empresa_id == empresa_id,
                Convite.accepted_at.is_(None),
                Convite.expires_at > now,
            )
        )
        for old in existing.scalars().all():
            await db.delete(old)

        token = secrets.token_urlsafe(32)
        convite = Convite(
            email=normalized,
            empresa_id=empresa_id,
            role=role,
            token_hash=_hash_token(token),
            invited_by_user_id=invited_by_user_id,
            expires_at=now + timedelta(days=INVITE_EXPIRY_DAYS),
        )
        db.add(convite)
        await db.flush()
        return convite, token

    async def get_pending_by_email(self, db: AsyncSession, email: str) -> Convite | None:
        normalized = _normalize_email(email)
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Convite)
            .where(
                Convite.email == normalized,
                Convite.accepted_at.is_(None),
                Convite.expires_at > now,
            )
            .order_by(Convite.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def send_invite_email_for_convite(
        self,
        db: AsyncSession,
        convite: Convite,
    ) -> None:
        settings = get_settings()
        empresa = await db.get(Empresa, convite.empresa_id)
        if not empresa:
            raise ValueError("Empresa not found")

        redirect_to = f"{settings.frontend_url.rstrip('/')}/auth/confirm"
        magic_link = await generate_magic_link(convite.email, redirect_to)
        await send_invite_email(convite.email, magic_link, empresa.nome, convite.role.value)

    async def mark_invite_accepted(self, db: AsyncSession, convite: Convite) -> None:
        if convite.accepted_at is None:
            convite.accepted_at = datetime.now(timezone.utc)
            await db.flush()

    async def accept_invite(
        self,
        db: AsyncSession,
        convite: Convite,
        user_id: uuid.UUID,
        nome: str,
    ) -> Funcionario:
        now = datetime.now(timezone.utc)
        if convite.accepted_at is not None:
            raise ValueError("Convite já foi aceito")
        if convite.expires_at <= now:
            raise ValueError("Convite expirado")

        existing = await db.execute(
            select(Funcionario).where(
                Funcionario.empresa_id == convite.empresa_id,
                Funcionario.user_id == user_id,
            )
        )
        existing_funcionario = existing.scalar_one_or_none()
        if existing_funcionario:
            trimmed = nome.strip()
            if trimmed and existing_funcionario.nome != trimmed:
                existing_funcionario.nome = trimmed
            convite.accepted_at = now
            await db.flush()
            return existing_funcionario

        funcionario_role = (
            FuncionarioRole.GESTOR if convite.role == ConviteRole.GESTOR else FuncionarioRole.OPERADOR
        )
        funcionario = Funcionario(
            empresa_id=convite.empresa_id,
            user_id=user_id,
            role=funcionario_role,
            nome=nome.strip(),
            is_active=True,
        )
        convite.accepted_at = now
        db.add(funcionario)
        await db.flush()
        return funcionario


invite_service = InviteService()
